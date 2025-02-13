# Generated by Django 4.1.4 on 2023-02-13 10:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "walletapp",
            "0038_remove_transactions_check_transaction_status_consistency_and_more",
        ),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="transactions",
            name="check_transaction_status_consistency",
        ),
        migrations.AlterField(
            model_name="transactions",
            name="type",
            field=models.CharField(
                choices=[
                    ("user", "User Transaction"),
                    ("internal", "Internal Transaction"),
                    ("fee", "Fee"),
                    ("minting", "Minting transaction"),
                    ("exchange", "Exchange"),
                ],
                default="",
                help_text="Transaction type",
                max_length=50,
            ),
        ),
        migrations.AddConstraint(
            model_name="transactions",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "inbound_invoice_waiting_for"),
                        ("type", "user"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", False),
                        ("invoice_outbound__isnull", True),
                        ("status", "inbound_invoice_generated"),
                        ("type", "user"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", False),
                        ("invoice_outbound__isnull", True),
                        ("status", "inbound_invoice_paid"),
                        ("type", "user"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "outbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", False),
                        ("status", "outbound_invoice_received"),
                        ("type", "user"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "outbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", False),
                        ("status", "outbound_invoice_paid"),
                        ("type", "user"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "outbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "placeholder_fee"),
                        ("type", "fee"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "outbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "fee_paid"),
                        ("type", "fee"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "minting_submitted"),
                        ("type", "minting"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "minting"),
                        ("type", "minting"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "tx_created"),
                        ("type", "minting"),
                    ),
                    models.Q(
                        ("destination_user__isnull", True),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "minted"),
                        ("type", "minting"),
                    ),
                    models.Q(
                        ("destination_user__isnull", False),
                        ("direction", "outbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "internal_stated"),
                        ("type", "internal"),
                    ),
                    models.Q(
                        ("destination_user__isnull", False),
                        ("direction", "outbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "internal_finished"),
                        ("type", "internal"),
                    ),
                    models.Q(
                        ("destination_user__isnull", False),
                        ("direction", "outbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "exchange_started"),
                        ("type", "exchange"),
                    ),
                    models.Q(
                        ("destination_user__isnull", False),
                        ("direction", "outbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "exchange_finished"),
                        ("type", "exchange"),
                    ),
                    models.Q(
                        ("destination_user__isnull", False),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "exchange_started"),
                        ("type", "exchange"),
                    ),
                    models.Q(
                        ("destination_user__isnull", False),
                        ("direction", "inbound"),
                        ("invoice_inbound__isnull", True),
                        ("invoice_outbound__isnull", True),
                        ("status", "exchange_finished"),
                        ("type", "exchange"),
                    ),
                    ("status", "error"),
                    _connector="OR",
                ),
                name="check_transaction_status_consistency",
            ),
        ),
    ]
