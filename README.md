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
inclusion. Right now, you need to list them as explicit directory arguments to
Tsutsumu. For most Python tools and applications, that means bundling the Python
code you are developing and all *runtime* dependencies, passing a distinct
directory to Tsutsumu for each package in the bundle. Automating package
selection based on a project's `pyproject.toml` is the obvious next step.

When Tsutsumu traverses the root directories provided as arguments, it currently
selects only a few textual formats for inclusion in the bundle. Notably, that
includes plain text, Markdown, ReStructured Text, HTML, CSS, JavaScript, and
Python. Out of those, Tsutsumu only executes Python code. The other files serve
as resources. Adding support for Base85-encoded binary formats seems like a good
idea, too.


## 3. The Workings of a Bundle

Conveniently, Tsutsumu's source repository contains the `spam` package for
illustrating the inner workings of Python module bundles. That package includes
the `__main__` and `bacon` modules as well as a very stylish `ham.html` webpage.
Let's turn that package into a bundle:

```py
>>> import tsutsumu
>>> maker = tsutsumu.BundleMaker(['spam'])
>>> maker
<tsutsumu-maker spam>
>>>
```

The bundle maker first scans the input directories for files to include in the
bundle. For each such file, it yields a `Path` and a `str`. The former is the
absolute, system-specific path for accessing the local file. The latter is the
relative path from the root directory, using '/' as path separator. It serves as
file name in the bundle script.

Since the relative paths are platform-independent, let's check them out:

```py
>>> files = list(sorted(maker.list_files(), key=lambda f: f[1]))
>>> for _, key in files:
...     print(key)
spam/__init__.py
spam/__main__.py
spam/bacon.py
>>>
```

Most bundle maker methods are generators that yield newline-terminated
bytestrings with the source code of the bundle script. We could use a helper
function that display those lines as text:

```py
>>> def show(lines):
...     for line in lines:
...         print(line.decode('utf8'), end='')
...
>>>
```

The inner `print()` statement converts each line from `bytes` to `str`. Since
each line already includes a line terminator, the `print()` statement also uses
the empty string for `end`ing the line.


### 3.1 Layout of Bundled Files

Tsutsumu represents the bundled files as a dictionary mapping file name strings
to file content bytestrings. But instead of assigning that dictionary to a
variable, which would force all modules into memory for the entire runtime of
the script, it does not keep the `dict` around. In fact, it also places it on a
false conditional branch:

```py
>>> START = tsutsumu.maker._BUNDLE_START_IFFY
>>> START
b'if False: {\n'
>>> show(START.splitlines(keepends=True))
if False: {
>>>
```

Now we can emit the code for each file name, content pair:

```py
>>> show(maker.emit_text_file(*files[0]))
# ------------------------------------------------------------------------------
"spam/__init__.py": b"print('spam/__init__.py')\n",
>>> show(maker.emit_text_file(*files[1]))
# ------------------------------------------------------------------------------
"spam/__main__.py":
b"""print('spam/__main__.py')
import spam.bacon
""",
>>> show(maker.emit_text_file(*files[2]))
# ------------------------------------------------------------------------------
"spam/bacon.py": b"print('spam/bacon.py')\n",
>>>
```

Having emitted all bundled files, we can close the dictionary literal.

```py
>>> tsutsumu.maker._BUNDLE_STOP
b'}\n\n'
>>>
```


### 3.2 A Bundle's Manifest: Offsets and Lengths

We have included the bundled files in the bundle script. They are formatted as a
Python `dict` literal so that the script remains parseable. But how do we
actually access the bundled files. While emitting each file entry, the bundle
maker was recording the offsets and lengths of the bytestring for each file.


```py
>>> show(maker.emit_manifest())
# ==============================================================================
<BLANKLINE>
MANIFEST = {
    "spam/__init__.py": (275, 30),
    "spam/__main__.py": (408, 51),
    "spam/bacon.py": (559, 27),
}
<BLANKLINE>
>>>
```

Tsutsumu's source repository not only includes the `spam` package. It also
contains `can.py`, a script bundling that package. If you look at `can.py`'s
manifest, you'll find that the offsets and lengths are the same as the ones
shown above. That means, we can use the file for simulating how a bundle reads,
say, `spam/bacon.py`:

```py
>>> with open('can.py', mode='rb') as file:
...     _ = file.seek(559)
...     data = file.read(27)
...
>>> data
b'b"print(\'spam/bacon.py\')\\n"'
>>>
```

As you can see, the data includes not only the file contents, but also the
leading and trailing characters for turning the file contents into a valid
Python bytestring literal. We need those decorations so that the bundle script
is parsable. But why read those characters?

Python bytestring literals may only contain ASCII characters; all other code
points must be escaped. It still is a reasonable format for representing the
file contents of mostly Python code, since the code itself heavily favors ASCII.
But there will be escape sequences. In fact, the above example already contains
an escaped newline character: `\\n`—notice the double backslash.

As it turns out, there is a very simple solution to turning these bytestring
literals into actual bytes: Just evaluate them!

```py
>>> eval(data)
b"print('spam/bacon.py')\n"
>>>
```

We can confirm that two consecutive `b` prefixes and two consecutive backslash
characters turned into one each, just as expected.


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


## 4. importlib.resources Considered Harmful

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


### 4.1 Use get_data()

Here's an example for how `get_data()` works. A module's loader is accessed
through the corresponding *spec* record.

```py
>>> import tsutsumu.maker
>>> tsutsumu.maker.__spec__                   # doctest: +ELLIPSIS
ModuleSpec(name='tsutsumu.maker', loader=..., origin=...)
>>> tsutsumu.maker.__spec__.loader            # doctest: +ELLIPSIS
<_frozen_importlib_external.SourceFileLoader object at ...>
>>> tsutsumu.maker.__spec__.loader.get_data   # doctest: +ELLIPSIS
<bound method FileLoader.get_data of <...>>
```


## 5. What's Missing?

There are two features I'd like to add to Tsutsumu in the near future. They seem
both highly desirable and reasonably straightforward to implement.

  * [ ] Automatically determining module dependencies
  * [ ] Including binary files in bundles
  * [ ] Bundling namespace packages.

---

Tsutsumu is © 2023 Robert Grimm and has been released under the Apache 2.0 license.
