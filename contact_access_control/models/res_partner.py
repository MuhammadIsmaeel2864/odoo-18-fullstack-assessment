
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    contact_category = fields.Selection(
        [
            ("customer", "Sales Lead / Customer"),
            ("vendor", "Vendor / Supplier"),
            ("employee", "Employee"),
            ("visitor", "Front Desk / Visitor"),
            ("general", "General / Internal"),
        ],
        string="Contact Category",
        required=True,
        default=lambda self: self._default_contact_category(),
    )

    def _get_allowed_categories(self):
        """Find categories the current user can create."""

        all_categories = {
            "customer", "vendor", "employee",
            "visitor", "general",
        }

        # Allow Odoo's internal superuser operations.
        if self.env.su:
            return all_categories

        user = self.env.user

        if user.has_group(
            "contact_access_control.group_contact_manager"
        ):
            return all_categories

        group_map = {
            "group_commercial": "customer",
            "group_procurement": "vendor",
            "group_hr": "employee",
            "group_front_desk": "visitor",
        }

        allowed = set()

        for group_name, category in group_map.items():
            if user.has_group(
                f"contact_access_control.{group_name}"
            ):
                allowed.add(category)

        return allowed

    def _default_contact_category(self):
        allowed = self._get_allowed_categories()

        for category in (
            "customer", "vendor", "employee",
            "visitor", "general"
        ):
            if category in allowed:
                return category

        return "general"

    def _check_category_permission(self, category):
        if category not in self._get_allowed_categories():
            raise AccessError(_(
                "You are not allowed to create or assign "
                "contacts with category '%s'."
            ) % category)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._get_allowed_categories():
            raise AccessError(_(
                "You do not have permission to create contacts. "
                "Please contact your administrator."
            ))

        prepared = []

        for values in vals_list:
            vals = dict(values)

            if vals.get("parent_id"):
                parent = self.browse(vals["parent_id"]).exists()

                if not parent:
                    raise ValidationError(_(
                        "The selected parent contact does not exist."
                    ))

                # Child contacts inherit their parent's category.
                vals["contact_category"] = parent.contact_category

            else:
                vals.setdefault(
                    "contact_category",
                    self._default_contact_category()
                )

            self._check_category_permission(
                vals["contact_category"]
            )
            prepared.append(vals)

        return super().create(prepared)

    def write(self, vals):
        vals = dict(vals)

        if vals.get("parent_id"):
            parent = self.browse(vals["parent_id"]).exists()

            if not parent:
                raise ValidationError(_(
                    "The selected parent contact does not exist."
                ))

            vals["contact_category"] = parent.contact_category

        if "contact_category" in vals:
            category = vals["contact_category"]
            self._check_category_permission(category)

            for partner in self:
                parent = (
                    self.browse(vals["parent_id"])
                    if "parent_id" in vals
                    else partner.parent_id
                )

                if parent and category != parent.contact_category:
                    raise ValidationError(_(
                        "A child contact must have the same "
                        "category as its parent."
                    ))

        result = super().write(vals)

        # Keep descendants synchronized when a parent's
        # category or parent changes.
        if "contact_category" in vals:
            for partner in self:
                if partner.child_ids:
                    partner.child_ids.write({
                        "contact_category": partner.contact_category
                    })

        return result


        
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        result = super().fields_get(
            allfields=allfields,
            attributes=attributes,
        )

        field_info = result.get("contact_category")

        if field_info and "selection" in field_info:
            allowed = self._get_allowed_categories()

            field_info["selection"] = [
                (value, label)
                for value, label in field_info["selection"]
                if value in allowed
            ]

        return result

