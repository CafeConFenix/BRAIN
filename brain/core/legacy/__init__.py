"""
Names BRAIN used before version 2.0.0 (when the program was in Spanish).

Every ``brain/core/legacy/<area>.py`` file describes, for one area, what changed so
that the data of an existing installation keeps working (see ``brain.core.migrate``).
Each file may define any of these (all optional):

    FOLDERS     {"old folder or file name": "new name"}   renames inside the data folder
    FILES       {"old.json": "new.json"}                  same, for file names
    KEYS        {"titulo": "title"}                       JSON keys, at any depth
    VALUES      {"kind": {"recordatorio": "reminder"}}    values of a JSON key (new name),
                                                          for a string or a list of strings
    RAW         ("field",)                                JSON fields holding user text
                                                          as keys: their content is left alone
    SQL_TABLES  {"peso": "weight"}                        old table -> new table
    SQL_COLUMNS {"weight": {"fecha": "date"}}             new table -> {old column: new column}
    SQL_VALUES  {("notices", "kind"): {"recordatorio": "reminder"}}
"""
