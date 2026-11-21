# The public package is the CLI only

The repo holds two UIs (`PAE.py`, a Tkinter desktop app, and `PAE_webapp.py`, a Streamlit app) and the shared engine. We publish `patautoedit` to PyPI as a command-line package. The wheel contains the `patautoedit` package and the `patautoedit` command; it does not contain `PAE.py`, `PAE_webapp.py`, `Sample/`, `test/`, or `.streamlit/`. The UIs stay in the repo and run from a checkout.

The web app carries internal hostnames and a deployment-specific password check, the Tk app needs a desktop, and `Sample/` holds customer-like ATPs. Shipping any of them publicly would leak internal context and add dependencies the CLI does not need. The CLI has no runtime dependencies, so `pip install` stays small and works on a headless machine.

A PyPI user gets the editor, not the GUIs. Adding a UI to the package later is a new decision, not a packaging detail. The CLI's JSON output and exit codes are a public contract; a future agent skill will call the CLI.
