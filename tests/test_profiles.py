from tests.helpers import CaseBrain


class TestProfiles(CaseBrain):
    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_add_and_list_people(self):
        self.execute("add_person", name="Ana")
        self.execute("add_person", name="Luis")

        r = self.execute("list_people")

        self.assertEqual([p["name"] for p in r["people"]], ["Ana", "Luis"])

    def test_adding_the_same_person_twice_does_not_duplicate(self):
        self.execute("add_person", name="Ana")
        self.execute("add_person", name="ana")

        self.assertEqual(len(self.execute("list_people")["people"]), 1)

    def test_empty_name_raises_an_error(self):
        with self.assertRaises(ValueError):
            self.execute("add_person", name="")

    def test_no_people_message(self):
        r = self.execute("list_people")

        self.assertIn("no people", r["message"])

    def test_remove_person(self):
        self.execute("add_person", name="Ana")
        self.execute("remove_person", name="Ana")

        self.assertEqual(self.execute("list_people"), {"message": "There are no people yet. I can add them to split chores and habits."})

    def test_removing_an_unknown_person_raises_an_error(self):
        with self.assertRaises(ValueError):
            self.execute("remove_person", name="Nobody")
