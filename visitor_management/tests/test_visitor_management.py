from unittest import TestCase
from datetime import datetime, timedelta

from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError, ValidationError


class TestVisitorManagement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Log = cls.env["visitor.log"].sudo()

        cls.visitor = cls.env["res.partner"].sudo().create({
            "name": "Automated Test Visitor",
            "contact_category": "visitor",
        })

        cls.host = cls.env["hr.employee"].sudo().create({
            "name": "Automated Test Host",
        })

    def _create_visit(self, **extra_values):
        values = {
            "visitor_id": self.visitor.id,
            "host_id": self.host.id,
            "purpose": "Automated Assessment Test",
        }
        values.update(extra_values)
        return self.Log.create(values)

    def test_01_create_visitor_log(self):
        visit = self._create_visit()

        self.assertTrue(visit.name.startswith("VIS/"))
        self.assertEqual(visit.state, "draft")
        self.assertEqual(visit.visitor_id, self.visitor)
        self.assertEqual(visit.host_id, self.host)

    def test_02_check_in(self):
        visit = self._create_visit()

        visit.action_check_in()

        self.assertEqual(visit.state, "checked_in")
        self.assertTrue(visit.check_in)
        self.assertFalse(visit.check_out)

    def test_03_check_out(self):
        visit = self._create_visit()

        visit.action_check_in()
        visit.action_check_out()

        self.assertEqual(visit.state, "checked_out")
        self.assertTrue(visit.check_out)
        self.assertGreaterEqual(
            visit.check_out,
            visit.check_in,
        )

    def test_04_prevent_overlapping_visits(self):
        first_visit = self._create_visit()
        first_visit.action_check_in()

        second_visit = self._create_visit()

        with TestCase.assertRaises(
            self, (ValidationError, UserError)
        ), self.env.cr.savepoint():
            second_visit.action_check_in()

    def test_05_cancel_and_reset(self):
        visit = self._create_visit()

        visit.action_cancel()
        self.assertEqual(visit.state, "cancelled")

        visit.action_reset_draft()
        self.assertEqual(visit.state, "draft")
        self.assertFalse(visit.check_in)
        self.assertFalse(visit.check_out)

    
    def test_06_reject_early_checkout(self):
        visit = self._create_visit()
        visit.action_check_in()

        invalid_checkout = (
            visit.check_in - timedelta(minutes=10)
        )

        with TestCase.assertRaises(
            self, (ValidationError, UserError)
        ), self.env.cr.savepoint():
            visit.write({
                "check_out": invalid_checkout,
            })


    def test_07_cron_does_not_checkout_early(self):
        visit = self._create_visit()
        visit.action_check_in()

        # 16:00 UTC = 21:00 PKT
        visit.write({
            "check_in": datetime(2026, 10, 12, 16, 0),
        })

        # 18:58 UTC = 23:58 PKT
        self.Log._cron_auto_checkout(
            now=datetime(2026, 10, 12, 18, 58)
        )

        self.assertEqual(visit.state, "checked_in")
        self.assertFalse(visit.check_out)

    def test_08_cron_at_1159_pm(self):
        visit = self._create_visit()
        visit.action_check_in()

        visit.write({
            "check_in": datetime(2026, 10, 12, 16, 0),
        })

        # 18:59 UTC = 23:59 PKT
        result = self.Log._cron_auto_checkout(
            now=datetime(2026, 10, 12, 18, 59)
        )

        self.assertEqual(result, 1)
        self.assertEqual(visit.state, "checked_out")
        self.assertEqual(
            visit.check_out,
            datetime(2026, 10, 12, 18, 59),
        )

    def test_09_delayed_cron_preserves_new_visits(self):
        old_visit = self._create_visit()
        old_visit.action_check_in()
        old_visit.write({
            "check_in": datetime(2026, 10, 12, 16, 0),
        })

        second_visitor = self.env[
            "res.partner"
        ].sudo().create({
            "name": "After Midnight Visitor",
            "contact_category": "visitor",
        })

        new_visit = self._create_visit(
            visitor_id=second_visitor.id
        )
        new_visit.action_check_in()

        # 19:02 UTC = 00:02 PKT, next day.
        new_visit.write({
            "check_in": datetime(2026, 10, 12, 19, 2),
        })

        # Cron runs six minutes late.
        self.Log._cron_auto_checkout(
            now=datetime(2026, 10, 12, 19, 5)
        )

        self.assertEqual(old_visit.state, "checked_out")
        self.assertEqual(
            old_visit.check_out,
            datetime(2026, 10, 12, 18, 59),
        )

        self.assertEqual(new_visit.state, "checked_in")
        self.assertFalse(new_visit.check_out)

    def test_10_report_configuration(self):
        report = self.env.ref(
            "visitor_management.action_report_visitor_badge"
        )

        self.assertEqual(report.model, "visitor.log")
        self.assertEqual(report.report_type, "qweb-pdf")
        self.assertEqual(
            report.report_name,
            "visitor_management.report_visitor_badge",
        )

    def test_11_front_desk_access(self):
        group = self.env.ref(
            "contact_access_control.group_front_desk"
        )

        user = self.env["res.users"].sudo().create({
            "name": "Visitor Test Front Desk",
            "login": "visitor_test_front_desk",
            "groups_id": [
                (6, 0, [
                    self.env.ref("base.group_user").id,
                    group.id,
                ])
            ],
        })

        self.assertTrue(
            self.env["visitor.log"]
            .with_user(user)
            .has_access("create")
        )

    def test_12_unassigned_user_denied(self):
        user = self.env["res.users"].sudo().create({
            "name": "Visitor Test Unassigned",
            "login": "visitor_test_unassigned",
            "groups_id": [
                (6, 0, [
                    self.env.ref("base.group_user").id,
                ])
            ],
        })

        self.assertFalse(
            self.env["visitor.log"]
            .with_user(user)
            .has_access("create")
        )

        with self.assertRaises(
            AccessError
        ), self.env.cr.savepoint():
            self.env["visitor.log"].with_user(
                user
            ).create({
                "visitor_id": self.visitor.id,
                "host_id": self.host.id,
                "purpose": "Unauthorized Test",
            })
