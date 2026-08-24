# Synthetic demo provenance

The demo contains no committed PPTX, receipt, screenshot, customer file, or
production evidence. `generate_demo.py` constructs every OOXML part from fixed
public strings, uses fixed ZIP metadata, and writes a small one-slide PPTX plus
an explicitly synthetic JSON evidence file at runtime.

`run_demo.py` creates those files in a temporary directory, runs the real
ArtifactProof `create` and `verify` commands, changes the temporary PPTX, and
confirms that verification rejects the change. The script uses a deliberately
public demo-only HMAC key and removes the temporary directory when it exits.
Child commands receive only a small allowlist of platform environment settings,
the repository source path, and that demo key; unrelated environment variables
are not forwarded.

The slide is an interoperability aid for the integrity workflow, not an example
of visual design quality, accessibility review, factual review, or delivery
proof. Generated output must not be committed or included in a release archive.

Run the temporary end-to-end demo from the repository root on Linux or macOS:

```bash
python3 examples/run_demo.py
```

On Windows PowerShell:

```powershell
py -3 examples\run_demo.py
```

To inspect the generated files on Linux or macOS, choose a new output
directory:

```bash
python3 examples/generate_demo.py --output-dir demo-output
```

On Windows PowerShell:

```powershell
py -3 examples\generate_demo.py --output-dir demo-output
```

The generator refuses to overwrite either expected output file. Remove the
generated directory before running a release privacy audit. If generation
fails after creating an output, that synthetic file is deliberately left in
place: the generator never deletes a path that another process could have
replaced. Inspect the directory and remove only files you have identified.
