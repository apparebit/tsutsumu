# Tsutsumu: A Python Module Bundler

> つつむ (tsutsumu), Japanese for bundle

Tsutsumu implements Python bundles, that is, Python scripts that contain several
modules or packages. That way, Tsutsumu enables self-contained scripts that can
run anywhere a suitable Python interpreter is available—*without* creating a
virtual environment or installing packages first.

Having said that, Tsutsumu isn't the only option for more easily distributing
Python code and it may very well not be the right option for your use case.
Notably, the standard library's
[`zipapp`](https://docs.python.org/3/library/zipapp.html) also compresses
bundled files and [pex](https://github.com/pantsbuild/pex) files further combine
bundling with virtual environments. That makes them more sophisticated but also
significantly more heavyweight. Tsutsumu's simplicity makes it best suited to
scripts that import a few dozen modules at most and should remain easily
readable and inspectable before execution.

The rest of this document covers Tsutsumu thusly:

 1. Just Download and Run!
 2. Make a Bundle
 3. The Workings of a Bundle
     1. Layout of Bundled Files
     2. A Bundle's Manifest: Offsets and Lengths
     3. On-Disk vs In-Memory
     4. Meta-Circular Bundling
     5. importlib.resources Considered Harmful
     6. Add a Resource Manifest Instead
 4. Still Missing


## 1. Just Download and Run!

There is nothing to install. There is no virtual environment to set up. Just
download [this file](tsutsumu.py) and run it:

```sh
% curl -o tsutsumu.py \
    "https://raw.githubusercontent.com/apparebit/tsutsumu/boss/tsutsumu.py"
% python tsutsumu.py -h
usage: tsutsumu [-h] [-b] [-o FILENAME] [-p PACKAGE] [-r] [-v]
                DIRECTORY [DIRECTORY ...]

Combine Python modules into a single, self-contained script that
...
```

Yup. I used Tsutsumu to bundle its own modules into `tsutsumu.py`. As a result,
getting started with Tsutsumu is as easy as downloading a file and running it.
Bundled scripts can be this easy and convenient!


### The Complicated Route Still Works

But just in case that you prefer to take the slow and familiar route, you can do
that, too. It just requires 3.5 times more command invocations and takes quite a
bit longer. But sure, here you go:

```sh
% mkdir tsutsumu
% cd tsutsumu
% python -m venv .venv
% source .venv/bin/activate
(.venv) % pip install --upgrade pip
(.venv) % pip install tsutsumu
(.venv) % python -m tsutsumu -h
usage: tsutsumu [-h] [-b] [-o FILENAME] [-p PACKAGE] [-r] [-v]
                DIRECTORY [DIRECTORY ...]

Combine Python modules into a single, self-contained script that
...
```

So how about bundling your Python modules?


## 2. Make a Bundle

The only challenge in making a bundle is in selecting the right directories for
inclusion. Right now, you need to list every package that should be included in
the bundle as a separate directory argument to Tsutsumu. Alas, for most Python
tools and applications, that's just the list of regular dependencies. While
module-level tree-shaking might still be desirable, automating package selection
based on a project's `pyproject.toml` is an obvious next step.

When Tsutsumu traverses provided directories, it currently limits itself to a
few textual formats based on file extension. In particular, it includes plain
text, Markdown, ReStructured Text, HTML, CSS, JavaScript, and most importantly
Python sources. Out of these, Tsutsumu only knows how to execute Python code.
The other files serve as resources. Adding support for Base85-encoded binary
formats seems like another obvious next step.


## 3. The Workings of a Bundle

This section is a hands-on exploration of Tsutsumu's inner workings. Its
implementation is split across three modules:

  * `tsutsumu.__main__` for the command line interface;
  * `tsutsumu.maker` for generating bundles with the `BundleMaker` class;
  * `tsutsumu.bundle` for importing from bundles with the `Bundle` class.

The `__main__` module isn't particularly interesting, so I focus on the latter
two, starting with the bundle maker. Conveniently, Tsutsumu's source repository
includes the `spam` package as an illustrative aid. In addition to its own
`__init__` package module, `spam` contains two Python modules, `__main__` and
`bacon` as well as a very stylish `ham.html` webpage.



By the way, all subsequent code examples have been validated with Python's
`doctest` tool.

```py
>>> import tsutsumu.maker
>>> maker = tsutsumu.maker.BundleMaker(['spam'])
>>> maker
<tsutsumu-maker spam>
>>>
```

The bundle maker ultimately needs to produce a Python script. To get there, the
bundle maker processes data from byte to file granularity, which is quite the
spread. Since it's easy enough to format strings to form entire lines and,
similarly, break larger blobs into individual lines, most bundle maker methods
treat the source line as the shared abstraction. However, since files are stored
as byte strings, not character strings, and byte counts do matter, those source
lines also are `bytes` (not `str`) and include newlines (just `\n`).

Having said that, the bundle maker starts out by iterating over the contents of
directories, yielding the files to be bundled. For each such file, it yields an
operating-system-specific `Path`—suitable for reading the file's contents from
the local file system—as well as a relative `str` key with forward slashes—for
identifying the file in the bundle's manifest. Here are the bundle maker's keys
for `spam`:

```py
>>> files = list(sorted(maker.list_files(), key=lambda f: f.key))
>>> for file in files:
...     print(file.key)
...
spam/__init__.py
spam/__main__.py
spam/bacon.py
spam/ham.html
>>>
```

Those are just the four files we expected:

  * `spam/__init__.py` contains `spam`'s package module;
  * `spam/__main__.py` is the package's main entry point;
  * `spam/bacon.poy` contains the `spam.bacon` submodule;
  * `spam/ham.html` is a package resource.


### 3.1 Layout of Bundled Files

Now that we know which files to include in the bundle, we can turn to their
layout in bundle scripts. The current format tries to reconcile two
 contradictory requirements: First, the layout must be valid Python source code.
That pretty much limits us to string literals for file names and contents.
Furthermore, since the collection of file names and contents obviously forms a
mapping, we might as well use a `dict` literal for the file data.

Second, the code must not retain the bundled data. Otherwise, all bundled files
are loaded into memory at startup and remain there for the duration of the
application's runtime. Ideally, the Python runtime doesn't even instantiate the
`dict` literal and just scans for its end. To facilitate that, the bundle script
does not assign the `dict` literal to a variable and, on top of that, includes
it only inside an `if False:` branch.

```py
>>> writeall = tsutsumu.maker.BundleMaker.writeall
>>> writeall(tsutsumu.maker._BUNDLE_START_IFFY.splitlines(keepends=True))
if False: {
>>>
```

I'm not sure whether CPython actually takes this use case into account during
parsing. In fact, I'd be surprised if it did. However, I also do know that
Donald Knuth's TeX (which dates back to the late 1970s) does optimize just this
case: Once TeX knows that a conditional branch is not taken, it scans upcoming
tokens, taking only `\if` (and variations thereof), `\else`, and `\fi` into
account, until it has found the end of the branch, resuming regular processing
thereafter.

In the hope that Python is just as clever, we next emit the dictionary contents
as file name, content pairs for each bundled file. We start with
`spam/__init__.py`:

```py
>>> writeall(maker.emit_text_file(*files[0]))
# ------------------------------------------------------------------------------
"spam/__init__.py": b"print('spam/__init__.py')\n",
>>>
```

As illustrated above, the file name or key is a `str` literal, whereas the file
contents are a `bytes` literal. The latter is more appropriate for file contents
because files store bytestrings, too. That means that bundle maker is yielding
lines of bytestrings that contain string and bytestring literals both. Ooh...

Let's process the other three files:

```py
>>> writeall(maker.emit_text_file(*files[1]))
# ------------------------------------------------------------------------------
"spam/__main__.py":
b"""print('spam/__main__.py')
import spam.bacon
<BLANKLINE>
print('also:', __file__)
""",
>>> writeall(maker.emit_text_file(*files[2]))
# ------------------------------------------------------------------------------
"spam/bacon.py": b"print('spam/bacon.py')\n",
>>> writeall(maker.emit_text_file(*files[3]))
# ------------------------------------------------------------------------------
"spam/ham.html":
b"""<!DOCTYPE html>
<html lang=en>
<meta charset=utf-8>
<title>Ham?</title>
<style>
* {
    margin: 0;
    padding: 0;
}
html {
    height: 100%;
}
body {
    min-height: 100%;
    display: grid;
    justify-content: center;
    align-content: center;
}
p {
    font-family: system-ui, sans-serif;
    font-size: calc(32vmin + 4vmax);
    font-weight: bolder;
}
</style>
<p>Ham!
""",
>>>
```

Now we can close the dictionary again:

```py
>>> writeall(tsutsumu.maker._BUNDLE_STOP.splitlines(keepends=True))
}
<BLANKLINE>
>>>
```


### 3.2 A Bundle's Manifest: Offsets and Lengths

A bundle's files are encoded as a `dict` literal by design—so that the script
parses—but are *not* assigned to any variable by design as well—so that the
script does not retain access to the data, which would only increase memory
pressure. So if the script doesn't retain a reference to the data, how does
it access the data when it's needed?

I've already hinted at the solution: While turning file names and contents into
yielded lines of the bundle script, the bundle maker tracks the byte offset and
length of each content literal. It helps that the bundle maker is implemented as
a class with several methods that are generators instead of as a bunch of
generator functions. That way, accumulating state while yielding lines only
requires another method call, with the state stored by the bundle maker
instance. It also helps that the bundle maker emits bundle contents first, at
the beginning of the content script and that it relies on named string constants
for the boilerplate before, between, and right after the file contents
dictionary.

Once the bundle maker is done with the file contents, it emits the manifest
with the offset and length for each file included in the bundle:

```py
>>> writeall(maker.emit_manifest())
# ==============================================================================
<BLANKLINE>
MANIFEST = {
    "spam/__init__.py": (304, 30),
    "spam/__main__.py": (437, 77),
    "spam/bacon.py": (614, 27),
    "spam/ham.html": (741, 382),
}
>>>
```

The data collected while yielding the file contents is one datum more granular
than offset and length. But the generator for the manifest consumes the output
of another generator that accumulates the original three length values per file.
As you can see, Tsutsumu's not so secret sauce are generator functions and
methods!

Tsutsumu's source repository does not just include the `spam` package. But its
collection of [prebundled scripts](https://github.io/apparebit/tsutsumu/bundles)
includes [`can.py`](), which already bundles the package. If you check
`can.py`'s contents, you should see the exact same files in the same order with
the same offsets and lengths. That means that we can use the bundle to
illustrate how the bundle runtime reads a file such as `spam/bacon.py`:

```py
>>> with open('bundles/can.py', mode='rb') as file:
...     _ = file.seek(614)
...     data = file.read(27)
...
>>> data
b'b"print(\'spam/bacon.py\')\\n"'
>>>
```

As you can see, the returned bytes aren't just the file contents, but also the
leading and trailing characters necessary for turning the contents into a valid
Python bytestring literal. We need those "decorations" in the script, so that
Python knows to parse the bytestring. But why read those extra characters?

Python bytestring literals represent 256 values per byte with ASCII characters
only. As a result, some code points necessarily require escape sequences. In
fact, there are more code points that require escaping than printable ASCII
characters. Nonetheless, this is a reasonable encoding for this domain because
Python source code draws on ASCII mostly and remains human-readable under the
encoding.

Still, we can't escape escape sequences—as the above example illustrates. Notice
the trailing `\\n`? That's an escaped newline taking up two bytes in the
bytestring. So why read a bytestring, as indicated by the leading `b'`,
containing a bytestring literal, as indicated by the subsequent `b"`, when we
really want proper bytes?

Here's why:

```py
>>> eval(data)
b"print('spam/bacon.py')\n"
>>>
```

It only takes an `eval` to turn two consecutive bytestring prefixes and
backslash characters into one each, producing real `bytes`.


### 3.3 On-Disk vs In-Memory

As presented so far, **bundled files are named by relative paths with forward
slashes**. That makes sense for bundle scripts while they are inert and being
distributed. After all, the raison d'être for Tsutsumu's bundle scripts is to be
easily copied to just about any computer and run right there. That wouldn't be
practical if the names used in the bundle were tied to the originating file
system or limited to some operating system only.

However, the naming requirements change fundamentally the moment a bundle starts
to execute on some computer. That instance should seamlessly integrate with the
local Python runtime and operating system, while also tracking provenance, i.e.,
whether modules originate from the bundle or from the local machine. In other
words, a **running bundle uses absolute paths with the operating system's path
segment separator**. Sure enough, the constructor for `tsutsumu.bundle.Bundle`
performs the translation from relative, system-independent paths to absolute,
system-specific paths by joining the absolute path to the bundle script with
each key.

Let's see how that plays out in practice on the example of the `can.py` bundle:

```py
>>> import bundles.can
>>> MANIFEST = bundles.can.MANIFEST
>>> for key in MANIFEST.keys():
...     print(key)
...
spam/__init__.py
spam/__main__.py
spam/bacon.py
spam/ham.html
>>>
```

Clearly, the `MANIFEST` is using relative paths.

Since `bundles.can` isn't `__main__`, importing the bundle resulted in the
definition of the `MANIFEST` dictionary and the `Bundle` class but it did not
install a new `Bundle` instance in the module loading machinery. Before we
manually install the bundle, there's a bit of housekeeping to do. We need to cut
off our ability to load modules from the regular file system. Otherwise, we
might inadvertently import the `spam` package from its sources and get mightily
confused. (Not that that ever happened to me...)

```py
>>> bundles.can.Bundle.restrict_sys_path()
>>> import spam
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ModuleNotFoundError: No module named 'spam'
>>>
```

No more readily available `spam`? Time to open `bundles.can`:

```py
>>> from pathlib import Path
>>> CAN = Path('.').absolute() / 'bundles' / 'can.py'
>>> can_content = bundles.can.Bundle.install(CAN, MANIFEST)
>>> import spam
spam/__init__.py
>>>
```

W00t, our supply of spam is secured. That's great. But how does it work? What
did `Bundle.install()` do exactly?

Well, a `Bundle` is what `importlib`'s documentation calls an *importer*, a
class that is both a *meta path finder* and a *loader*. When Python tries to
load a module that hasn't yet been loaded, it (basically) invokes
`find_spec(name)` on each object in `sys.meta_path`, asking that meta path
finder whether it recognizes the module. If the meta path finder does, it
returns a description of the module. Most fields of that *spec* are just
informative, i.e., strings, but one field, surprisingly called `loader`, is an
object with methods for loading and executing the module's Python code. It just
happens that `Bundle` does not delegate to a separate class for loading but does
all the work itself.

In short, `Bundle.install()` creates a new `Bundle()` and makes that bundle the
first entry of `sys.meta_path`.

Ok. But what about the bundle using absolute paths?

```py
>>> for key in can_content._manifest.keys():
...     path = Path(key)
...     assert path.is_absolute()
...     print(str(path.relative_to(CAN)).replace('\\', '/'))
...
spam/__init__.py
spam/__main__.py
spam/bacon.py
spam/ham.html
>>>
```

Clearly, the installed `can_content` bundle is using absolute paths. Also, each
key now starts with the bundle script's path, which we recreated in `CAN`. While
we usually don't worry much about these paths when importing modules in Python,
we do need to use them when loading resources from a package:

```py
>>> data = can_content.get_data(CAN / 'spam' / 'ham.html')
>>> data[-5:-1]
b'Ham!'
>>>
```

Ham! it is. Unless: My apologies for the ham-fisted humor to all vegetarians.
But then again, I'm sure that you were imagining suitable plant-based
alternatives all along. Ham! it is.


### 3.4 Meta-Circular Bundling

Tsutsumu can bundle any application that is not too large and written purely in
Python. That includes itself. Tsutsumu can bundle itself because it avoids the
file system when including its own `tsutsumu/bundle.py` in the bundle script.
Instead, it uses the module loader's `get_data()` method, which is designed for
accessing packaged resources and whose use I just demonstrated.

One drawback of Tsutsumu treating its own source code just like other Python
files is the effective duplication of `tsutsumu/bundle.py`, once as part of the
bundled files and once as part of the bundle script itself. While that may be
desirable, for example, when experimenting with a new version of Tsutsumu, it
also wastes almost 8 kb. To avoid that overhead, you can use the
`-r`/`--repackage` command line option when bundling Tsutsumu. Under that
option, Tsutsumu special cases the `tsutsumu` and `tsutsumu.bundle` modules and
recreates them during startup—with `tsutsumu`'s `bundle` attribute referencing
the `tsutsumu.bundle` module and `tsutsumu.bundle`'s `Bundle` attribute
referencing the corresponding class.


## 3.5 importlib.resources Considered Harmful

While Tsutsumu does support `Loader.get_data()`, it does *not* support the more
recent `Loader.get_resource_reader()` and probably never will. The API simply is
too complex for what it does, i.e., providing yet another way of traversing a
hierarchy of directory-like and file-like entities. Furthermore, the
documentation's claims about the benefits of integration with Python's import
machinery seem farfetched at best.

A look at the 8 (!) modules implementing `importlib.resources` in the standard
library bears this out: In addition to the documented `ResourceReader`,
`Traversable`, and `TraversableReader` abstract classes, there are undocumented
`FileReader`, `ZipReader`, and `NamespaceReader` implementations, the
`SimpleReader` fallback implementation, and the `CompatibilityFiles` adapter.
Furthermore, since `Traversable` is designed to have "a subset of `pathlib.Path`
methods," the code in `importlib.resources` makes heavy use of the `Path`
implementations provided by `pathlib` and `zipfile`. Taken together, that's a
lot of code for exposing a hierarchy of directory- and file-like entities.
Worse, despite the documentation's claims to the contrary, none of this code
leverages core `importlib` machinery—besides hanging off loaders and hence
touching on `ModuleType` and `ModuleSpec`. In fact, it doesn't even integrate
with the previous resource API, the much simpler `get_data()` method on loaders.
In summary, `importlib.resources` does not offer what it claims and is far too
complex for what it offers. It should be scrapped!


### 3.6 Add a Resource Manifest Instead

When you compare the two ways of accessing resources, `Loader.get_data()` and
`Loader.get_resource_reader()`, the latter obviously wins on traversing a
package's namespace. But that's a non-feature when it comes to resource access.
When code needs a resource, it shouldn't need to search for the resource by
searching them all, it should be able to just access the resource, possibly
through one level of indirection. In other words, if a package's resources may
vary, the package should include a resource manifest at a well-known location,
say, `manifest.toml` relative to the package's path. Once the package includes a
manifest, `Loader.get_data()` more than suffices for retrieving resources.
`Loader.get_resource_reader()` only adds useless complexity.


## 4. Still Missing

I believe that Tsutsumu is ready for real-world use. However, since it hasn't
seen wide usage, I'd hold off on mission-critical deployments for now.
Meanwhile, Tsutsumu could use a few more features. I can think of three:

  * [ ] Automatically determine module dependencies
  * [ ] Support inclusion of binary files in bundles
  * [ ] Support the bundling of namespace packages

What else?

---

Tsutsumu is © 2023 Robert Grimm and has been released under the Apache 2.0 license.
