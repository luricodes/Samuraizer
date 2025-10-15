# Samuraizer Log Panel Modernization Plan

## 1. Objectives
- Deliver a responsive log viewer that remains smooth with tens of thousands of records.
- Provide accurate filtering, searching, and theming without mutating global logging state.
- Modularize the logging pipeline so UI, data model, and log ingestion can evolve independently.

## 2. Current State Assessment
- `LogPanel` relies on `QTextEdit` as an append-only buffer and manually tracks the number of lines to enforce limits, including custom cursor gymnastics to evict the oldest entry.【F:samuraizer/gui/windows/main/panels/log_panel.py†L172-L307】
- Changing the log level filter directly mutates the root logger level and repopulates the view by reformatting the entire buffer, which couples the widget to global logging configuration and causes unnecessary work.【F:samuraizer/gui/windows/main/panels/log_panel.py†L308-L337】
- `GuiLogHandler` emits pre-formatted strings with baked-in colors, making theme integration and advanced formatting (e.g., per-field styling) difficult. Buffer management is tightly coupled to the handler, and there is no way to emit structured data (thread name, module, etc.) without revisiting the entire pipeline.【F:samuraizer/utils/log_handler.py†L24-L159】
- Search operations delegate to `QTextEdit.find`, which becomes sluggish with large documents and does not expose match counts or global filtering options.【F:samuraizer/gui/windows/main/panels/log_panel.py†L338-L365】

## 3. Technology Evaluation
### 3.1 Widget Options
1. **QPlainTextEdit**
   - Pros: Optimized for large plain text, lower memory overhead than QTextEdit.
   - Cons: Still relies on a monolithic document; colored ranges require costly extra formats and do not virtualize rows. Limited support for structured layouts (icon + timestamp + message).
2. **QSyntaxHighlighter** (paired with text editors)
   - Pros: Built-in pattern-based highlighting.
   - Cons: Runs on the entire document; for long logs it repeatedly scans the complete buffer and does not help with structured metadata columns.
3. **Model/View (`QAbstractListModel` + `QListView`/`QTreeView`)**
   - Pros: Native item virtualization, lazy data access, straightforward filtering via proxy models, easy to render per-field widgets (icons, colored labels) via delegates, integrates with Qt's MVC patterns.
   - Cons: Requires a custom model and delegate implementation.
4. **Qt 6 `QListView` with `QML` or `QQuickWidget`**
   - Pros: Rich styling, GPU-accelerated rendering.
   - Cons: Introduces QML runtime into an existing QWidget-based app and complicates theming/state persistence.

**Recommendation:** Adopt a model/view architecture using `QListView` (or `QTreeView` for multi-column layouts) backed by a specialized log model. This approach delivers virtualization, structured rendering, and clean separation between data, view, and theming while staying within the current QWidget ecosystem.

## 4. Target Architecture
```
+--------------------+          +-------------------+          +----------------------+
| logging.Logger(s)  |  emit    | GuiLogHandler     |  signal  | LogIngestController  |
+--------------------+ -------> +-------------------+ -------> +----------------------+
                                                            |    |  - thread-safe queue|
                                                            |    |  - throttled batching|
                                                            v    +----------------------+
                                                      +-----------------+
                                                      | LogStore        |<---> persisted settings
                                                      | (ring buffer)   |
                                                      +-----------------+
                                                            |
                                                            v
                                                      +-----------------+
                                                      | LogListModel    |
                                                      +-----------------+
                                                            |
                                                            v
                                                      +-----------------+
                                                      | LogFilterProxy  |
                                                      +-----------------+
                                                            |
                                                            v
                                                      +-----------------+
                                                      | LogPanel view   |
                                                      +-----------------+
```

### Components
- **LogIngestController**: Converts handler signals into queued tasks processed on the GUI thread, decoupling ingestion cadence from UI updates.
- **LogStore**: Maintains a fixed-size ring buffer of structured `LogRecordPayload` objects. Supports slicing, iteration, and metadata lookups without forcing the handler to carry UI state.
- **LogListModel** (`QAbstractListModel`): Exposes fields (timestamp, level, message, module, thread) via roles. Supports partial fetch (fetchMore) and notifying views of incremental additions/removals.
- **LogFilterProxy** (`QSortFilterProxyModel` subclass): Applies severity thresholds, text queries, time ranges, and regex flags without touching the global logger level. Provides match counts for UI badges.
- **Delegate/Renderer**: Custom `QStyledItemDelegate` to render icons, colored badges, and multi-line text while honoring theme colors.
- **LogPanel Widget**: Hosts toolbar controls, the view, status indicators, and integrates with application settings.

## 5. Implementation Phases
### Phase 0 – Foundations
- Define a `LogRecordPayload` dataclass capturing structured fields (timestamp, level, logger name, thread, message, traceback, extra metadata).
- Extend `GuiLogHandler` to emit payloads (while still supporting legacy formatted strings during migration). Introduce a dedicated color provider that defers theme selection to the view layer.【F:samuraizer/utils/log_handler.py†L24-L159】
- Introduce comprehensive unit tests for the handler buffer, including batch flushing and buffer resizing edge cases.

### Phase 1 – Data Layer
- Implement `LogStore` as a thin wrapper over `collections.deque` with deterministic eviction hooks so the UI model can be notified when rows are removed.
- Build `LogListModel` to consume the store. Ensure `data`, `rowCount`, and `roleNames` operate purely on structured payloads.
- Add `LogFilterProxy` to handle severity filtering, free-text search (case sensitivity, regex), and optional module filtering. Expose API to compute the number of visible rows for UI counters.

### Phase 2 – Presentation Layer
- Replace the `QTextEdit` widget with a `QTreeView` in list mode (single column) or `QListView` configured for uniform item sizes. Bind it to the proxy model.
- Develop a delegate that paints: level badge (colored rectangle or icon), timestamp (monospace), truncated message preview, and expand/collapse affordance for multi-line payloads. Defer colors to a `ThemePalette` helper that reads from `ThemeManager` (light/dark variants).【F:samuraizer/gui/app/theme_manager.py†L14-L105】
- Implement virtualization-friendly features (row height caching, `uniformItemSizes`, `batchInsert` updates) to keep rendering O(visible rows).

### Phase 3 – Interaction & UX
- Recreate toolbar controls using model APIs: severity combo sets proxy filter, search box applies filter string, auto-scroll toggles follow-last-row behavior.
- Add advanced filters: toggle timestamp visibility, show only messages from selected subsystems, quick buttons for errors/warnings.
- Provide a detail pane (optional splitter) that shows full log payload, including structured fields and formatted traceback when a row is selected.
- Update context menu to offer copy selected rows, copy full payload (JSON/plain text), export filtered results, and “mute logger” shortcuts.

### Phase 4 – Settings & Persistence
- Store per-user preferences (columns, severity level, search options, buffer size, auto-scroll) through `QSettings`, keeping backwards compatibility with existing keys where sensible.【F:samuraizer/gui/windows/main/panels/log_panel.py†L48-L136】
- Persist `GuiLogHandler` configuration (batch size, interval) via the same mechanism used in `ResultsViewWidget.setupLogging` so command-line runs can reuse preferences.【F:samuraizer/gui/widgets/analysis_viewer/main_viewer.py†L170-L199】
- Offer a migration path to clear obsolete settings (e.g., ones tied to QTextEdit behavior).

### Phase 5 – Diagnostics & Testing
- Instrument ingestion and rendering with lightweight metrics (e.g., average append latency, queue depth) surfaced through the status bar or debug logs.
- Create automated tests: model filtering correctness, buffer eviction, theme palette mapping, serialization of exports, and GUI smoke tests via `pytest-qt`.
- Add load-testing utility that replays synthetic log streams to validate performance at 50k+ entries.

## 6. Migration Strategy
1. Land data-layer changes (`LogRecordPayload`, handler updates) while still feeding the old widget to ensure backwards compatibility.
2. Introduce the new model/view components behind a feature flag (QSettings toggle or environment variable) to allow dogfooding.
3. Once stable, remove the legacy QTextEdit implementation and delete transitional code paths.
4. Provide a fallback mode (toggle to plain text) for environments where delegates misbehave, simplifying troubleshooting.

## 7. Risk & Mitigation
- **Performance regression**: Guard with load tests and profiling; keep payload copying minimal by passing references through the store.
- **Theme mismatches**: Centralize colors in a theme-aware palette service and connect to theme change signals so the view repaints without restart.
- **Threading issues**: All handler emissions already occur on worker threads. Ensure the ingest controller marshals payloads to the GUI thread via `QMetaObject.invokeMethod` or queued connections.
- **User familiarity**: Preserve existing shortcuts (Ctrl+F for search, Ctrl+A for select all) and keep toolbar layout similar to minimize relearning.

## 8. Stretch Goals
- Add log grouping (collapsible by task or logger name) via nested models.
- Provide in-panel analytics: severity histogram, live counters.
- Support exporting filtered logs to JSON/CSV directly from the proxy model.
- Integrate with external tail sources (e.g., file tailer) by swapping the ingest controller with a plugin.

## 9. Deliverables
- Updated `GuiLogHandler` with structured payloads and tests.
- New `logging` package module housing `LogStore`, models, and theme palette utilities.
- Refactored `LogPanel` widget using the model/view stack with enhanced UX.
- Developer documentation describing extension points and theming hooks (this document remains the canonical roadmap).

