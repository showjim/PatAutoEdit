# Expanded MTO patterns are not compiled

An expanded MTO pattern keeps its `(mto = …)` lines and is input for a separate tool that generates the MTO data and removes the MTO microcode; it is not compiled or run as is. IG-XL rejects MTO microcode in VM modules (`apc` 11.10.00: "MTO/MPG extended microcodes are not allowed in VM modules"), and SRM, where loops run, holds only about 1,000 vectors, so a fully expanded MTO pattern cannot run on the tester. Expand Loop still expands MTO modules, but warns once per file that the output cannot be compiled.
