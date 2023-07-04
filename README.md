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
bundled files and [pex](https://github.com/pantsbuild/pex) files combine
bundling with virtual environments. Compared to Tsutsumu, they are more complex
and more suitable for large applications. In contrast, Tsutsumu is best suited
for scripts that import several dozen modules at most and should remain easily
readable and inspectable before execution.


## 1. Just Download and Run!

There is nothing to install. There is no virtual environment to set up. Just
download [this file](tsutsumu.py) and run it:

```sh
$ curl -o tsutsumu.py \
    "https://raw.githubusercontent.com/apparebit/tsutsumu/boss/tsutsumu.py"
$ python tsutsumu.py -h
usage: tsutsumu [-h] [-o FILE] [-p PKG] [-r] [-v] DIR [DIR ...]

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
$ mkdir tsutsumu
$ cd tsutsumu
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install --upgrade pip
$ pip install tsutsumu
$ python -m tsutsumu -h
usage: tsutsumu [-h] [-o FILE] [-p PKG] [-r] [-v] DIR [DIR ...]

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
  * `tsutsumu.bundle` for running modules with the `Bundle` class.

The `__main__` module isn't particularly interesting, so I focus on the latter
two, starting with the bundle maker. Conveniently, Tsutsumu's source repository
includes the `spam` package as an illustrative aid. In addition to its own
`__init__` package module, `spam` contains two Python modules, `__main__` and
`bacon` as well as a very stylish `ham.html` webpage. (Please do check it out
🙄). Now, let's get started turning those files into a bundle.

```py
>>> import tsutsumu.maker
>>> maker = tsutsumu.maker.BundleMaker(['spam'])
>>> maker
<tsutsumu-maker spam>
>>>
```

The bundle maker ultimately needs to produce a Python script. To get there, the
bundle maker processes data from file granularity, when including them in the
bundle, down to character granularity, when tracking each file's offset from the
start of the file and length. It also creates Python source code one dictionary
key at a time, i.e., at line granularity. Since it's easy enough to format
strings to form entire lines and, similarly, easy enough to break larger blobs
into lines, most bundle maker methods are generators that yield lines. In fact,
they yield lines of `bytes` (not `str`) that include newlines (just `\n`).

The following function helps us print such binary lines:

```py
>>> def show(lines):
...     for line in lines:
...         print(line.decode('utf8'), end='')
...
>>>
```

It consumes all lines produced by a generator, decoding each line as UTF-8 and
printing it without adding another newline, hence the `end` keyword argument.

We won't get to `show()` right away, however, because the bundle maker doesn't
just start yielding lines out of nowhere but instead starts by yielding paths to
the bundled files. In fact, for each file, it yields an
operating-system-specific `Path`—suitable for reading the file's contents from
the local file system—as well as a relative `str` key with forward slashes—for
identifying the file in the bundle's manifest. Here are bundle maker's keys for
`spam`:

```py
>>> file_ordering = tsutsumu.maker.BundleMaker.file_ordering
>>> files = list(sorted(maker.list_files(), key=file_ordering))
>>> for _, key in files:
...     print(key)
...
spam/__init__.py
spam/__main__.py
spam/bacon.py
spam/ham.html
>>>
```

Sure enough, bundle maker yields four files:

  * `spam/__init__.py` with the `spam` package module;
  * `spam/__main__.py` with the package's main entry point;
  * `spam/bacon.poy` with the `spam.bacon` submodule;
  * `spam/ham.html` as a package resource.


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
>>> show(tsutsumu.maker._BUNDLE_START_IFFY.splitlines(keepends=True))
if False: {
>>>
```

I don't know whether, for instance, CPython optimizes script parsing for this
use case. I do know that Donald Knuth's TeX (which goes back to the late 1970s)
does not parse conditional branches known to be false and instead scans
subsequent tokens until it reaches the closest command sequence ending the
branch.

In any case, we next emit the dictionary contents as file name, content pairs
for each bundled file. We start with `spam/__init__.py`:

```py
>>> show(maker.emit_text_file(*files[0]))
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
>>> show(maker.emit_text_file(*files[1]))
# ------------------------------------------------------------------------------
"spam/__main__.py":
b"""print('spam/__main__.py')
import spam.bacon
<BLANKLINE>
print('also:', __file__)
""",
>>> show(maker.emit_text_file(*files[2]))
# ------------------------------------------------------------------------------
"spam/bacon.py": b"print('spam/bacon.py')\n",
>>> show(maker.emit_text_file(*files[3]))
# ------------------------------------------------------------------------------
"spam/ham.html":
b"""<!doctype html>
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
>>> show(tsutsumu.maker._BUNDLE_STOP.splitlines(keepends=True))
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
>>> show(maker.emit_manifest())
# ==============================================================================
<BLANKLINE>
MANIFEST = {
    "spam/__init__.py": (304, 30),
    "spam/__main__.py": (437, 77),
    "spam/bacon.py": (614, 27),
    "spam/ham.html": (741, 382),
}
<BLANKLINE>
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

It only takes one `eval` to turn two consecutive bytestring prefixes and
backslash characters into one each, producing real `bytes` just as desired.


### 3.3 On-Disk vs In-Memory

When file paths appear in the bundle script, they always are relative and only
use forward slashes as path separators, no matter the operating system. That is
consistent with the fact that the bundle script is designed for flexible
distribution and that bundled files only exist relative to the bundle script.
However, when executing the bundle script, the runtime rewrites all paths to use
the local operating system's path separator. It also makes them absolute by
joining the bundle script's absolute path with the bundled file's relative path.
Doing so clearly und uniquely identifies a module's origin, even if a runtime
loads several bundles. It also avoids constant translation between external and
internal paths.

The on-disk script and the in-memory bundle differ significantly in two aspects:
First, on disk, the bundle script uses relative file paths with forward slashes,
independent of operating system. That is consistent with Tsutsumu's goal of
running whereever a suitable Python is available. In memory, however, the bundle
uses absolute paths consistent with the local operating system's separator.
Those paths combine the absolute path for the running bundle script with the
relative path of the bundled file. As a result, each module path uniquely and
clearly identifies its provenance.

Since every bundle script ships with the contents of the `tsutsumu.bundle`
module, including that same module

The second difference is that the `tsutsumu.bundle` package is incorporated into
the bundle script. But just before handing over to `runpy`'s `run_module()`, the
bundle script removes itself from `sys.modules`, thus making it impossible to
reference the `Bundle` class. To make avoid effectively including the same
source file twice when bundling Tsutsumu itself, the bundle repackages itself


### 3.4 Meta-Circular Bundling

Tsutsumu bundles other Python applications, no problem. It can also bundle
itself, no problem. That works because Tsutsumu avoid the file system API when
including its own `tsutsumu/bundle.py` in the bundle script. It instead uses the
module loader's `get_data()` method, which is designed for access to resources
bundled with modules and packages.

That does duplicate the source code for `tsutsumu/bundle.py` in the bundle
script, once as part of the bundled files and once as part of the bundle script
runtime. While that may be advantageous, e.g., when experimenting with new
versions, it also wastes about 7,600 bytes. To avoid that overhead, you can use
the `-r`/`--repackage` option when bundling Tsutsumu. When that option is
enabled, Tsutsumu special-cases the `tsutsumu` and `tsutsumu.bundle` modules and
recreates them during startup—with `tsutsumu`'s `bundle` attribute referencing
the `tsutsumu.bundle` module and `tsutsumu.bundle`'s `Bundle` attribute
referencing the corresponding class. No other attributes are defined.

The critical enabling factor for meta-circular bundling is the `get_data()`
method. Since Tsutsumu's own loader implements the method, once Tsutsumu runs as
a bundle script, it's bound to work. Python's regular file system loader
currently supports the method as well. But since it has been deprecated, it may
stop doing so in the future. For that reason, Tsutsumu falls back on the file
system when possible. Alas, I have some thoughts about the supposed replacement
for the `get_data()` method, `importlib.resources`.


## 3.5 importlib.resources Considered Harmful

Tsutsumu does *not* support `importlib`'s interface for retrieving resources and
probably never will. The API simply is too complex for what it does, i.e.,
providing yet another way of traversing a hierarchy of directory-like and
file-like entities. Furthermore, the documentation's claims about the benefits
of integration with Python's import machinery are rather dubious, at the very
best.

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


### 3.6 Use Loader.get_data() Instead

Instead of `importlib.resources`, I recommend using `Loader.get_data()`. Despite
being only one method, it suffices. If you know available resources and their
relative paths within the package, all you need to do is look up the package's
`__path__` or another module's `__file__` and graft the resource path onto it
before handing over the combined path to `Loader.get_data()`.

```py
TODO
```

If you do not know available resources and their relative paths, you are
screwed. At least, you cannot discover available resources unless, that is, the
package maintainers include some form of resource manifest at a well-known
location. With a little preparation, a single method is almost as powerful as
`importlib.resources`. In fact, I believe that a resource manifest is highly
desirable even in the presence of an API supporting arbitrary traversal because
it tells you where to find what resource instead of making you search.


## 4. What's Missing?

I believe that Tsutsumu is ready for some real experimentation. But it hasn't
seen the usage needed to be ready for usage in mission critical scenarios. It
definitely could use a few more features. I can think of three:

  * [ ] Automatically determine module dependencies
  * [ ] Support inclusion of binary files in bundles
  * [ ] Support the bundling of namespace packages

What else?

---

Tsutsumu is © 2023 Robert Grimm and has been released under the Apache 2.0 license.
