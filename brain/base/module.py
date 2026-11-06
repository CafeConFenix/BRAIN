from brain.core.data_manager import DataManager


class ModuleBase:
    """
    Common base for BRAIN's modules.

    Each module stores its data in data/<name>/<name>.json, split into
    sections (lists of records). Modules never touch files directly:
    everything goes through the DataManager.
    """

    name = ""

    def __init__(self):
        self.data = DataManager()

    def add_record(self, section, record):
        self.data.add_record(
            module=self.name,
            section=section,
            record=record,
        )

    def get_section(self, section):
        data = self.data.read_module(self.name)

        value = data.get(section, [])

        if not isinstance(value, list):
            return []

        return value

    def save_section(self, section, records):
        data = self.data.read_module(self.name)

        data[section] = records

        self.data.save_module(self.name, data)

    def sections(self):
        """Returns the module's section names."""

        return list(self.data.read_module(self.name).keys())
