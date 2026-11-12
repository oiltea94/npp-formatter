# Build dependencies

- Notepad++ SDK headers: tag v8.8.8, commit
  `9d87ac96d14d10224d6f8f0c1b3033b1b61cb969`, from
  https://github.com/notepad-plus-plus/notepad-plus-plus.
  PluginInterface.h and Notepad_plus_msgs.h are GPL-3.0-or-later.
- Scintilla.h and Sci_Position.h: the same Notepad++ tag, scintilla/include;
  see npp/Scintilla-LICENSE.txt.
- nlohmann/json 3.12.0 single-header release:
  https://github.com/nlohmann/json/tree/v3.12.0, MIT.

Node.js and Prettier are not redistributed. The Prettier development dependency
is used only by tests; the release ZIP is assembled from an explicit file list.
