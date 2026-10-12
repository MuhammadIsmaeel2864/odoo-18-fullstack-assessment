
{
    "name": "Front Desk Visitor Management",
    "version": "18.0.1.0.0",
    "summary": "Manage visitor registration and attendance",
    "category": "Human Resources",
    "author": "Assessment Developer",

    "depends": [
        "base",
        "contacts",
        "contact_access_control",
        "hr",
        "mail",
    ],

    "data": [
    "security/ir.model.access.csv",
    "data/visitor_sequence.xml",
    "data/visitor_cron.xml",
    "views/visitor_views.xml",
    "views/visitor_menus.xml",
    "report/visitor_badge.xml",
],

    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
