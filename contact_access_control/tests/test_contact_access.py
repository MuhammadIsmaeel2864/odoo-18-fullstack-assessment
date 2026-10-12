
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestContactAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Internal users also need Odoo's standard
        # Contact Creation access for allowed cases.
        cls.internal_group = cls.env.ref("base.group_user")
        cls.contact_acl_group = cls.env.ref(
            "base.group_partner_manager"
        )

        cls.commercial = cls._make_user(
            "commercial", "group_commercial"
        )
        cls.procurement = cls._make_user(
            "procurement", "group_procurement"
        )
        cls.hr = cls._make_user(
            "hr", "group_hr"
        )
        cls.front_desk = cls._make_user(
            "frontdesk", "group_front_desk"
        )
        cls.manager = cls._make_user(
            "manager", "group_contact_manager"
        )
        cls.ungrouped = cls._make_user("ungrouped")

    @classmethod
    def _make_user(cls, login, control_group=None):
        groups = [
            cls.internal_group.id,
            cls.contact_acl_group.id,
        ]

        if control_group:
            group = cls.env.ref(
                f"contact_access_control.{control_group}"
            )
            groups.append(group.id)

        return cls.env["res.users"].sudo().create({
            "name": f"Test {login}",
            "login": f"assessment_{login}",
            "groups_id": [(6, 0, groups)],
        })

    def _create_contact(self, user, name, category, **extra):
        vals = {
            "name": name,
            "contact_category": category,
        }
        vals.update(extra)

        return self.env["res.partner"].with_user(
            user
        ).create(vals)

    # ----------------------------------
    # ALLOWED CREATION TESTS
    # ----------------------------------

    def test_01_commercial_customer_allowed(self):
        partner = self._create_contact(
            self.commercial,
            "Test Customer",
            "customer",
        )
        self.assertEqual(
            partner.contact_category, "customer"
        )

    def test_02_procurement_vendor_allowed(self):
        partner = self._create_contact(
            self.procurement,
            "Test Vendor",
            "vendor",
        )
        self.assertEqual(
            partner.contact_category, "vendor"
        )

    def test_03_hr_employee_allowed(self):
        partner = self._create_contact(
            self.hr,
            "Test Employee",
            "employee",
        )
        self.assertEqual(
            partner.contact_category, "employee"
        )

    def test_04_frontdesk_visitor_allowed(self):
        partner = self._create_contact(
            self.front_desk,
            "Test Visitor",
            "visitor",
        )
        self.assertEqual(
            partner.contact_category, "visitor"
        )

    def test_05_manager_all_categories(self):
        for category in [
            "customer", "vendor", "employee",
            "visitor", "general"
        ]:
            partner = self._create_contact(
                self.manager,
                f"Manager {category}",
                category,
            )
            self.assertEqual(
                partner.contact_category, category
            )

    # ----------------------------------
    # DENIED CREATION TESTS
    # ----------------------------------

    def test_06_commercial_vendor_denied(self):
        with self.assertRaises(AccessError):
            self._create_contact(
                self.commercial,
                "Forbidden Vendor",
                "vendor",
            )

    def test_07_procurement_customer_denied(self):
        with self.assertRaises(AccessError):
            self._create_contact(
                self.procurement,
                "Forbidden Customer",
                "customer",
            )

    def test_08_hr_visitor_denied(self):
        with self.assertRaises(AccessError):
            self._create_contact(
                self.hr,
                "Forbidden Visitor",
                "visitor",
            )

    def test_09_ungrouped_user_denied(self):
        with self.assertRaises(AccessError):
            self._create_contact(
                self.ungrouped,
                "Unauthorized Contact",
                "general",
            )

    # ----------------------------------
    # CATEGORY CHANGE TEST
    # ----------------------------------

    def test_10_forbidden_category_change(self):
        partner = self._create_contact(
            self.commercial,
            "Commercial Customer",
            "customer",
        )

        with self.assertRaises(AccessError):
            partner.with_user(
                self.commercial
            ).write({
                "contact_category": "vendor"
            })

        self.assertEqual(
            partner.contact_category, "customer"
        )

    # ----------------------------------
    # CHILD CONTACT INHERITANCE
    # ----------------------------------

    def test_11_child_inherits_parent_category(self):
        parent = self._create_contact(
            self.manager,
            "Parent Customer",
            "customer",
        )

        child = self._create_contact(
            self.manager,
            "Child Contact",
            "vendor",
            parent_id=parent.id,
        )

        self.assertEqual(
            child.contact_category, "customer"
        )

    def test_12_child_creation_restricted(self):
        parent = self._create_contact(
            self.manager,
            "Parent Vendor",
            "vendor",
        )

        with self.assertRaises(AccessError):
            self._create_contact(
                self.commercial,
                "Forbidden Child",
                "customer",
                parent_id=parent.id,
            )

    # ----------------------------------
    # DROPDOWN METADATA TEST
    # ----------------------------------

    def test_13_commercial_selection_filtered(self):
        fields_info = self.env["res.partner"].with_user(
            self.commercial
        ).fields_get(
            ["contact_category"],
            ["selection"],
        )

        selection = fields_info[
            "contact_category"
        ]["selection"]

        allowed_values = {
            value for value, label in selection
        }

        self.assertEqual(
            allowed_values, {"customer"}
        )
