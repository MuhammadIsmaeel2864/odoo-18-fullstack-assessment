

from datetime import datetime, time, timedelta
import pytz
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class VisitorLog(models.Model):
    _name = "visitor.log"
    _description = "Visitor Management Log"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "check_in desc, id desc"

    # ----------------------------------
    # VISITOR FIELDS
    # ----------------------------------

    name = fields.Char(
        string="Reference",
        required=True,
        readonly=True,
        copy=False,
        default="New",
    )

    visitor_id = fields.Many2one(
        "res.partner",
        string="Visitor",
        required=True,
        domain=[("contact_category", "=", "visitor")],
        tracking=True,
    )

    host_id = fields.Many2one(
        "hr.employee",
        string="Host Employee",
        required=True,
    )

    purpose = fields.Text(
        string="Purpose of Visit",
        required=True,
    )

    check_in = fields.Datetime(
        string="Check-in Time",
        readonly=True,
        copy=False,
    )

    check_out = fields.Datetime(
        string="Check-out Time",
        readonly=True,
        copy=False,
    )

    duration = fields.Float(
        string="Duration (Hours)",
        compute="_compute_duration",
        store=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    # ----------------------------------
    # AUTOMATIC REFERENCE NUMBER
    # ----------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            reference = self.env[
                "ir.sequence"
            ].next_by_code("visitor.log")

            if not reference:
                raise UserError(_(
                    "Visitor sequence is not configured."
                ))

            vals["name"] = reference

        return super().create(vals_list)

    # ----------------------------------
    # COMPUTED DURATION
    # ----------------------------------

    @api.depends("check_in", "check_out")
    def _compute_duration(self):
        for record in self:
            if record.check_in and record.check_out:
                seconds = (
                    record.check_out - record.check_in
                ).total_seconds()

                record.duration = max(
                    seconds / 3600.0, 0.0
                )
            else:
                record.duration = 0.0

    # ----------------------------------
    # VALIDATE VISITOR CATEGORY
    # ----------------------------------

    @api.constrains("visitor_id")
    def _check_visitor_category(self):
        for record in self:
            if (
                record.visitor_id
                and record.visitor_id.contact_category != "visitor"
            ):
                raise ValidationError(_(
                    "Only contacts in the Visitor category "
                    "can be selected."
                ))

    # ----------------------------------
    # VALIDATE CHECK-IN / CHECK-OUT
    # ----------------------------------

    @api.constrains("check_in", "check_out", "state")
    def _check_visit_times(self):
        for record in self:
            if record.check_out and not record.check_in:
                raise ValidationError(_(
                    "Check-out requires a check-in time."
                ))

            if (
                record.check_in
                and record.check_out
                and record.check_out < record.check_in
            ):
                raise ValidationError(_(
                    "Check-out cannot be earlier than check-in."
                ))

            if record.state == "checked_in":
                if not record.check_in or record.check_out:
                    raise ValidationError(_(
                        "A checked-in visit must have a "
                        "check-in time and no check-out time."
                    ))

            if record.state == "checked_out":
                if not record.check_in or not record.check_out:
                    raise ValidationError(_(
                        "A checked-out visit requires "
                        "both check-in and check-out times."
                    ))

    # ----------------------------------
    # PREVENT OVERLAPPING VISITS
    # ----------------------------------

    @api.constrains(
        "visitor_id", "check_in", "check_out", "state"
    )
    def _check_overlapping_visits(self):
        for record in self:
            if (
                record.state not in ("checked_in", "checked_out")
                or not record.check_in
                or not record.visitor_id
            ):
                continue

            other_visits = self.search([
                ("visitor_id", "=", record.visitor_id.id),
                ("id", "!=", record.id),
                ("state", "in", [
                    "checked_in", "checked_out"
                ]),
                ("check_in", "!=", False),
            ])

            for other in other_visits:
                starts_before_other_ends = (
                    not other.check_out
                    or record.check_in < other.check_out
                )

                other_starts_before_end = (
                    not record.check_out
                    or other.check_in < record.check_out
                )

                if (
                    starts_before_other_ends
                    and other_starts_before_end
                ):
                    raise ValidationError(_(
                        "This visitor already has an "
                        "overlapping visit."
                    ))

    # ----------------------------------
    # CHECK IN
    # ----------------------------------

    def action_check_in(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_(
                    "Only draft visits can be checked in."
                ))

            record.write({
                "check_in": fields.Datetime.now(),
                "check_out": False,
                "state": "checked_in",
            })

    # ----------------------------------
    # CHECK OUT
    # ----------------------------------

    def action_check_out(self):
        for record in self:
            if record.state != "checked_in":
                raise UserError(_(
                    "Only checked-in visits can be checked out."
                ))

            record.write({
                "check_out": fields.Datetime.now(),
                "state": "checked_out",
            })

    # ----------------------------------
    # CANCEL VISIT
    # ----------------------------------

    def action_cancel(self):
        for record in self:
            if record.state not in ("draft", "checked_in"):
                raise UserError(_(
                    "Only draft or checked-in visits "
                    "can be cancelled."
                ))

            record.write({
                "state": "cancelled",
            })

    # ----------------------------------
    # RESET TO DRAFT
    # ----------------------------------

    def action_reset_draft(self):
        for record in self:
            if record.state != "cancelled":
                raise UserError(_(
                    "Only cancelled visits can be reset."
                ))

            record.write({
                "check_in": False,
                "check_out": False,
                "state": "draft",
            })

    # ----------------------------------
    # DAILY AUTOMATIC CHECK-OUT
    # ----------------------------------

    
    @api.model
    def _cron_auto_checkout(self, now=None):
        """Close visits active at the most recent 23:59 PKT cutoff."""

        utc_now = fields.Datetime.to_datetime(
            now if now is not None else fields.Datetime.now()
        )

        if utc_now.tzinfo is not None:
            utc_now = utc_now.astimezone(
                pytz.UTC
            ).replace(tzinfo=None)

        timezone = pytz.timezone("Asia/Karachi")

        local_now = pytz.UTC.localize(
            utc_now
        ).astimezone(timezone)

        cutoff_date = local_now.date()

        # Before 23:59, the last completed cutoff
        # belongs to the previous calendar day.
        if local_now.time() < time(23, 59):
            cutoff_date -= timedelta(days=1)

        local_cutoff = timezone.localize(
            datetime.combine(cutoff_date, time(23, 59))
        )

        utc_cutoff = local_cutoff.astimezone(
            pytz.UTC
        ).replace(tzinfo=None)

        visits = self.sudo().search([
            ("state", "=", "checked_in"),
            ("check_in", "!=", False),
            ("check_in", "<=", utc_cutoff),
        ])

        for visit in visits:
            visit.write({
                "check_out": utc_cutoff,
                "state": "checked_out",
            })

        return len(visits)

