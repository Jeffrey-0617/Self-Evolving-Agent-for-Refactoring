This trace shows a design refactoring that finished with a VALID result after the agent retrieved and applied knowledge distilled from earlier runs on other systems.

## 1. New requirement

> Provide domain-specific utility functionality by spliting ArchStudioUtils into domain-specific utility services: extract EditorUtils (serves EditorManager, ArchEdit, SharedEditorInfrastructure, and Launcher), AnalysisUtils (serves Archlight, TypeWrangler, GuardTracker, Schematron, and SelectorDriver), ModelUtils (serves XArchADT, XArchChangeSet, ChangeSetUtils, and ChangeSetRelationshipManager), and ViewUtils (serves Archipelago, GraphLayout, RationaleView, and TracelinkView) — each utility service must provide the same API contract as the original ArchStudioUtils ports it replaces, Resources must route resource requests to the appropriate domain utility, PreferencesADT must configure per-domain utility settings, Meta must access ModelUtils for metadata operations, and FileManager must use EditorUtils instead of the monolithic ArchStudioUtils.

## 2. Knowledge Retrieval

The retrieval results included relevant Episodes, Patterns, Skills, and previously generated Tools from prior runs.

### 2.1 Past experience from Eshop

- **Episode:** payment-fraud service integration
  - **Pattern:** `port-isolation-for-dual-input-roles`
    - **Skill (guidance):** `reusableskill-connector-rules`
  - **Pattern:** `until-assertion-csp-anti-pattern`
    - **Skill (guidance):** `reusableskill-assertion-design`
  - **Pattern:** `assertion-event-name-mismatch`
    - **Skill (guidance):** `reusableskill-assertion-design`
    - **Skill (tool-backed):** `check-assertion-events`
    - **Tool (previously generated):** `check_assertion_events`
- **Episode:** decomposition of `ShopBackend`
  - **Pattern:** `backend-split-decomposition-topology`
    - **Skill (guidance):** `reusableskill-connector-rules`

### 2.2 Past experience from Rideshare

- **Episode:** scheduled-ride booking integration
  - **Pattern:** `duplicate-port-name-across-components`
    - **Skill (tool-backed):** `check-port-name-uniqueness`
    - **Tool (previously generated):** `check_port_name_uniqueness`

### 2.3 Past experience from Lifenet

- **Episode:** insurance-subsystem integration
  - **Pattern:** `adl-file-no-assert-statements`
    - **Skill (tool-backed):** `check-adl-no-asserts`
    - **Tool (previously generated):** `check_adl_no_asserts`

## 3. Refactor based on past experience in the ArchStudio design
Only relevant structural summaries or partial specifications are displayed in the following content where needed.

### 3.1 caller allocation
- **Decision:** the agent inspected each caller's responsibility and assigned it to the appropriate utility.

The resulting structural allocation is summarized below. This is a design-level component mapping, not a formal property specification in Wright#:

```text
EditorUtils
  EditorManager, ArchEdit, SharedEditorInfrastructure, Launcher,
  FileManager, BooleanNotation, FileTracker, CopyPasteManager

AnalysisUtils
  Archlight, TypeWrangler, GuardTracker, Schematron,
  SelectorDriver, RelatedElements, ArchlightPrefs

ModelUtils
  XArchADT, XArchChangeSet, ChangeSetUtils,
  ChangeSetRelationshipManager, Meta, AIM,
  BasePreferences, EclipseContentStore, ExplicitADT

ViewUtils
  Archipelago, GraphLayout, RationaleView,
  TracelinkView, ArchipelagoPrefs
```

### 3.2 Retrieved topology patterns applied to ArchStudio

- **Episode — Eshop backend decomposition:** decomposition of `ShopBackend`.
  - **Pattern:** `backend-split-decomposition-topology`
- **Episode — Eshop payment-fraud integration:**
  - **Pattern:** `port-isolation-for-dual-input-roles`
- **Skill (guidance):** `reusableskill-connector-rules`
- **Source — original ArchStudio ADL:** callers already used separate **Connector type:** `CSConnector` connections to the monolithic **Component:** `ArchStudioUtils`.

The actual split-related ADL change was substantially larger than four attachments:

- four utility components were added with 37 ports in total
- 29 caller-to-utility paths were created for the caller allocation shown in Section 3.1;
- 74 endpoint attachments were added;
- **Component:** `PreferencesADT` replaced one monolithic port with four utility-specific ports;
- **Component:** `Resources` replaced one monolithic utility port with four utility-specific ports; and
- **Components:** `Schematron`, `SelectorDriver`, and `ChangeSetRelationshipManager` each gained one new output port.

The partial specification below intentionally displays only 4 paths considering readability, one per utility:

```wright#
connector CSConnector {
  role requester(j) = process -> req!j -> res?j -> Skip;
  role responder() = req?j -> invoke -> process -> res!j -> responder();
  ...
}

component EditorManager {
  port manager_util_call() = mgr_util_called -> manager_util_call();
  ...
}

component EditorUtils {
  port editorutils_srv_em() = eu_em_served -> editorutils_srv_em();
  ...
}

component Archlight {
  port call_al_util_service() = al_util_called -> call_al_util_service();
  ...
}

component AnalysisUtils {
  port analysisutils_srv_al() = au_al_served -> analysisutils_srv_al();
  ...
}

component XArchADT {
  port access_xarch_utils() = xarch_util_call -> access_xarch_utils();
  ...
}

component ModelUtils {
  port modelutils_srv_xadt() = mu_xadt_served -> modelutils_srv_xadt();
  ...
}

component Archipelago {
  port use_archstudio_utils() = arch_util_used -> use_archstudio_utils();
  ...
}

component ViewUtils {
  port viewutils_srv_arch() = vu_arch_served -> viewutils_srv_arch();
  ...
}

system archstudio {
  declare em_to_edutil = CSConnector;
  ...
  declare al_to_anutil = CSConnector;
  ...
  declare xadt_to_modutil = CSConnector;
  ...
  declare arch_to_viewutil = CSConnector;
  ...

  attach EditorManager.manager_util_call() = em_to_edutil.requester(30);
  attach EditorUtils.editorutils_srv_em() = em_to_edutil.responder();
  ...

  attach Archlight.call_al_util_service() = al_to_anutil.requester(15);
  attach AnalysisUtils.analysisutils_srv_al() = al_to_anutil.responder();
  ...

  attach XArchADT.access_xarch_utils() = xadt_to_modutil.requester(68);
  attach ModelUtils.modelutils_srv_xadt() = xadt_to_modutil.responder();
  ...

  attach Archipelago.use_archstudio_utils() = arch_to_viewutil.requester(20);
  attach ViewUtils.viewutils_srv_arch() = arch_to_viewutil.responder();
  ...
}
```

### 3.3 Retrieved port-naming safeguard applied to ArchStudio

- **Episode — Rideshare scheduled-ride booking:**
  - **Pattern:** `duplicate-port-name-across-components`
  - **Skill (tool-backed):** `check-port-name-uniqueness`

The retrieved naming safeguard prevented the four utilities from declaring colliding port names, which would result in misconfigurations.

### 3.4 Shared-provider connections after the utility split

This change was made during **Episode:** `ep-51` to satisfy the new requirement. **Component:** `PreferencesADT` had to configure every new utility, and every new utility had to access **Component:** `Resources`.

The diagrams below show the complete shared-provider topology for `PreferencesADT`, the four utility components, and `Resources`. They are not examples, but they cover only this shared-provider part of the refactoring; the 29 caller-to-utility paths from Section 3.1 are not repeated here.

Before **Episode:** `ep-51`, the structure was:

```text
PreferencesADT -> ArchStudioUtils -> Resources
```

After **Episode:** `ep-51`, the structure became:

```text
PreferencesADT -> EditorUtils   -> Resources
               -> AnalysisUtils -> Resources
               -> ModelUtils    -> Resources
               -> ViewUtils     -> Resources
```

All names in these two diagrams are components, and the arrows represent connections rather than Wright# ADL.

After the run, this design decision was recorded for future tasks as:

- **Pattern refined:** `backend-split-decomposition-topology`
- **Pattern variant added:** `Variant D: utility split`
- **Skill (guidance) updated:** `reusableskill-connector-rules`

The **Pattern variant:** `Variant D: utility split` is a named case inside the Pattern, not a separate Pattern or Skill.

## 4. Apply Tool-based skills for static analysis before formal verification

After generating the refactored design, the agent applied the previously generated Tool-based skills. Each Tool was used through its linked tool-backed Skill before formal verification. 
- **Skill (tool-backed):** `check-adl-no-asserts` used **Tool:** `check_adl_no_asserts` to verify that the refactored ADL contained no embedded assertions: PASS.
- **Skill (tool-backed):** `check-port-name-uniqueness` used **Tool:** `check_port_name_uniqueness` to verify global port-name uniqueness: PASS.
- **Skill (tool-backed):** `check-assertion-events` used **Tool:** `check_assertion_events` to verify every assertion event reference against its component port declaration: PASS.

## 5. Verification outcome

```text
Final outcome: VALID
```

## 6. Final design and properties

### 6.1 Partial topology before and after refactoring

The partial topologies before and after refactoring are displayed below. `...` represents additional components and connections that are not shown.

```text
BEFORE REFACTORING

PreferencesADT
      |
      | one configuration connection
      v
ArchStudioUtils
serves:
EditorManager
ArchEdit
Archlight
XArchADT
Archipelago
...
      |
      | one resource connection
      v
Resources
      |
     ...


AFTER REFACTORING

                              PreferencesADT
                                    |
                 four independent configuration connections
                                    |
          +-------------------------+-------------------------+-------------------------+
          |                         |                         |                         |
          v                         v                         v                         v
    EditorUtils               AnalysisUtils              ModelUtils                 ViewUtils
    EditorManager             Archlight                  XArchADT                   Archipelago
    ArchEdit                  TypeWrangler               XArchChangeSet             GraphLayout
    ...                       ...                        ...                        ...
          |                         |                         |                         |
          +-------------------------+-------------------------+-------------------------+
                                    |
                    four independent resource connections
                                    |
                                    v
                                Resources
                                    |
                                   ...
```

### 6.2 properties
```wright
assert archstudio |= [] (EditorManager.manager_util_call.mgr_util_called -> <> EditorUtils.editorutils_srv_em.eu_em_served);
assert archstudio |= [] (ArchEdit.edit_via_utils.edit_dispatched -> <> EditorUtils.editorutils_srv_ae.eu_ae_served);
assert archstudio |= [] (SharedEditorInfrastructure.shared_util_call.shared_util_called -> <> EditorUtils.editorutils_srv_sei.eu_sei_served);
assert archstudio |= [] (Launcher.launch_utils.utils_launched -> <> EditorUtils.editorutils_srv_lnch.eu_lnch_served);
assert archstudio |= [] (FileManager.file_util_call.file_util_called -> <> EditorUtils.editorutils_srv_fm.eu_fm_served);
assert archstudio |= [] (Archlight.call_al_util_service.al_util_called -> <> AnalysisUtils.analysisutils_srv_al.au_al_served);
assert archstudio |= [] (TypeWrangler.wrangle_utils.types_wrangled -> <> AnalysisUtils.analysisutils_srv_tw.au_tw_served);
assert archstudio |= [] (GuardTracker.track_guards.guards_tracked -> <> AnalysisUtils.analysisutils_srv_gt.au_gt_served);
assert archstudio |= [] (Schematron.schm_to_analysis_utils.schm_au_called -> <> AnalysisUtils.analysisutils_srv_schm.au_schm_served);
assert archstudio |= [] (SelectorDriver.sd_to_analysis_utils.sd_au_called -> <> AnalysisUtils.analysisutils_srv_sd.au_sd_served);
assert archstudio |= [] (XArchADT.access_xarch_utils.xarch_util_call -> <> ModelUtils.modelutils_srv_xadt.mu_xadt_served);
assert archstudio |= [] (XArchChangeSet.xarch_cs_archstudio_call.xarch_cs_arch -> <> ModelUtils.modelutils_srv_xcs.mu_xcs_served);
assert archstudio |= [] (ChangeSetUtils.cs_util_arch_call.cs_arch_called -> <> ModelUtils.modelutils_srv_csu.mu_csu_served);
assert archstudio |= [] (ChangeSetRelationshipManager.csrm_to_model_utils.csrm_mu_called -> <> ModelUtils.modelutils_srv_csrm.mu_csrm_served);
assert archstudio |= [] (Meta.meta_util_call.meta_util_called -> <> ModelUtils.modelutils_srv_meta.mu_meta_served);
assert archstudio |= [] (Archipelago.use_archstudio_utils.arch_util_used -> <> ViewUtils.viewutils_srv_arch.vu_arch_served);
assert archstudio |= [] (GraphLayout.layout_to_utils.layout_util_call -> <> ViewUtils.viewutils_srv_gl.vu_gl_served);
assert archstudio |= [] (RationaleView.view_rv_utils.rv_util_called -> <> ViewUtils.viewutils_srv_rv.vu_rv_served);
assert archstudio |= [] (TracelinkView.trace_links.links_traced -> <> ViewUtils.viewutils_srv_tlv.vu_tlv_served);
assert archstudio |= [] (PreferencesADT.padt_to_editor_utils.padt_eu_called -> <> EditorUtils.editorutils_srv_padt.eu_padt_served);
assert archstudio |= [] (PreferencesADT.padt_to_analysis_utils.padt_au_called -> <> AnalysisUtils.analysisutils_srv_padt.au_padt_served);
assert archstudio |= [] (PreferencesADT.padt_to_model_utils.padt_mu_called -> <> ModelUtils.modelutils_srv_padt.mu_padt_served);
assert archstudio |= [] (PreferencesADT.padt_to_view_utils.padt_vu_called -> <> ViewUtils.viewutils_srv_padt.vu_padt_served);
assert archstudio |= [] (EditorUtils.editorutils_to_res.eu_res_requested -> <> Resources.provide_editorutils_res.eu_res_provided);
assert archstudio |= [] (AnalysisUtils.analysisutils_to_res.au_res_requested -> <> Resources.provide_analysisutils_res.au_res_provided);
assert archstudio |= [] (ModelUtils.modelutils_to_res.mu_res_requested -> <> Resources.provide_modelutils_res.mu_res_provided);
assert archstudio |= [] (ViewUtils.viewutils_to_res.vu_res_requested -> <> Resources.provide_viewutils_res.vu_res_provided);
```

## 7. Knowledge Gained by this run

This run refined **Pattern:** `backend-split-decomposition-topology` by adding **Pattern variant:** `Variant D: utility split`.

**Pattern variant:** `Variant D: utility split` added three reusable rules:

1. classify unspecified callers by functional responsibility;
2. expand shared infrastructure providers from one port to N ports;
3. prefix every new utility's ports with the utility identity.

The **Pattern:** `backend-split-decomposition-topology` metadata now records eight references and links to **Skill (guidance):** `reusableskill-connector-rules`, where the operational design guidance is available to later runs.
