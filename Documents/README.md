# Current paper and editable source

Read `Research paper_reference_style.pdf`; the corresponding DOCX is editable.
The canonical content source for regeneration is
`Paper_Sources/Research paper_updated_authors.docx`.

The layout follows the supplied reference article's compact journal style.
It is not a certification of any publisher's submission requirements. The
full-width abstract replaces the former keywords block; Declarations and the
paper-outline paragraph were removed as requested. Authors, measured comparisons,
equations, readable charts and source/cross-reference links are retained.

To rebuild after editing the content source, from the repository root:

```powershell
py -m pip install -r Documents/requirements.txt
py Scripts/style_paper_like_reference.py
py Scripts/add_reference_links.py
py Scripts/link_paper_cross_references.py
```

Then export the styled DOCX to the same-named PDF in Microsoft Word and run:

```powershell
py Scripts/validate_paper.py
```

Rebuilding style replaces the styled DOCX, so the two hyperlink scripts must run
afterward. Editing only the styled document will not survive regeneration.
The validator checks exhibit numbering, author names, requested removals,
preserved equations, source links, internal destinations and experiment tables.

Paper provenance and verification records are under
`CP-1/Forecasting_v3_Results/Expanded_Analysis/yolo11/expanded_01/`.
