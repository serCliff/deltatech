# -*- coding: utf-8 -*-
# ©  2018 Deltatech
# See README.rst file on addons root folder for license details


from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class account_payment(models.Model):
    _inherit = "account.payment"

    statement_id = fields.Many2one('account.bank.statement', string='Statement',
                                   domain="[('journal_id','=',journal_id)]")

    statement_line_id = fields.Many2one('account.bank.statement.line', string='Statement Line', readonly=True,
                                        domain="[('statement_id','=',statement_id)]")

    @api.onchange('payment_date', 'journal_id')
    def onchange_date_journal(self):
        domain = [('date', '=', self.payment_date), ('journal_id', '=', self.journal_id.id)]
        statement = self.env['account.bank.statement'].search(domain, limit=1)
        if statement:
            self.statement_id = statement
        else:
            # daca tipul este numerar trebuie generat
            if self.journal_id.type == 'cash':
                name = False
                values = {
                    'journal_id': self.journal_id.id,
                    'date': self.payment_date,
                    'name': '/'
                }
                self.statement_id = self.env['account.bank.statement'].create(values)

    @api.multi
    def post(self):
        lines = self.env['account.bank.statement.line']
        statement_payment = {}

        for payment in self:
            detination_statement = False
            if not payment.statement_line_id and payment.statement_id:
                ref = ''
                for invoice in payment.invoice_ids:
                    ref += invoice.number
                for invoice in payment.reconciled_invoice_ids:
                    ref += invoice.number
                values = {
                    'name': payment.communication or '/',
                    'statement_id': payment.statement_id.id,
                    'date': payment.payment_date,
                    'partner_id': payment.partner_id.id,
                    'amount': payment.amount,
                    'payment_id': payment.id,
                    'ref':ref
                }
                if payment.payment_type in ['outbound', 'transfer']:
                    values['amount'] = -1 * payment.amount

                line = self.env['account.bank.statement.line'].create(values)
                lines |= line
                payment.write({'statement_line_id': line.id})
                statement_payment[payment] = {
                    'line': line
                }
                if payment.payment_type == 'transfer':
                    if payment.destination_journal_id.type == 'cash':
                        domain = [('date', '=', payment.payment_date),
                                  ('journal_id', '=', payment.destination_journal_id.id)]
                        detination_statement = self.env['account.bank.statement'].search(domain, limit=1)
                        if not detination_statement:
                            statement_values = {
                                'journal_id': payment.destination_journal_id.id,
                                'date': payment.payment_date,
                                'name': '/'
                            }
                            detination_statement = self.env['account.bank.statement'].create(statement_values)
                        values['statement_id'] = detination_statement.id
                        values['amount'] = payment.amount
                        line = self.env['account.bank.statement.line'].create(values)
                        lines |= line
                        statement_payment[payment]['line_destination'] = line

        res = super(account_payment, self).post()
        if lines:
            for line in lines:
                if line.name == '/':
                    line.write({'name': line.payment_id.name})
        self.reconciliation_statement_line()
        # for payment in self:
        #     for move_line in payment.move_line_ids:
        #         if not move_line.statement_id:
        #             if move_line.journal_id==payment.journal_id:
        #                 line = statement_payment[payment]['line']
        #             else:
        #                 line = statement_payment[payment]['line_destination']
        #             move_line.write({'statement_id': line.statement_id.id})
        #             move_line.move_id.write({'statement_line_id': line.id})
        #     if payment.payment_type == 'transfer':
        #         payment.write({'state': 'reconciled'})
        return res

    @api.multi
    def reconciliation_statement_line(self):
        for payment in self:
            if payment.move_reconciled:
                for move_line in payment.move_line_ids:
                    if not move_line.statement_id and not move_line.reconciled:
                        move_line.write({
                            'statement_id': payment.statement_id.id,
                            'statement_line_id': payment.statement_line_id.id
                        })
            else:
                raise UserError(_('Payment is not reconciled'))

    @api.multi
    def get_reconciled_statement_line(self):
        for payment in self:
            for move_line in payment.move_line_ids:
                if move_line.statement_id and move_line.statement_line_id:
                    payment.write({
                        'statement_id': move_line.statement_id.id,
                        'statement_line_id': move_line.statement_line_id.id
                    })

    @api.multi
    def add_statement_line(self):
        lines = self.env['account.bank.statement.line']
        self.get_reconciled_statement_line()
        for payment in self:

            if payment.journal_id.type == 'cash' and not payment.statement_id:
                domain = [('date', '=', self.payment_date), ('journal_id', '=', self.journal_id.id)]
                statement = self.env['account.bank.statement'].search(domain, limit=1)
                if not statement:
                    values = {
                        'journal_id': payment.journal_id.id,
                        'date': payment.payment_date,
                        'name': '/'
                    }
                    statement = payment.env['account.bank.statement'].create(values)
                payment.write({'statement_id': statement.id})

            if payment.state == 'posted' and not payment.statement_line_id and payment.statement_id:
                ref = ''
                for invoice in payment.invoice_ids:
                    ref += invoice.number
                for invoice in payment.reconciled_invoice_ids:
                    ref += invoice.number
                values = {
                    'name': payment.communication or payment.name,
                    'statement_id': payment.statement_id.id,
                    'date': payment.payment_date,
                    'partner_id': payment.partner_id.id,
                    'amount': payment.amount,
                    'payment_id': payment.id,
                    'ref':ref
                }
                if payment.payment_type in ['outbound', 'transfer']:
                    values['amount'] = -1 * payment.amount

                line = self.env['account.bank.statement.line'].create(values)
                lines |= line
                payment.write({'statement_line_id': line.id})

                if payment.payment_type == 'transfer':
                    payment.write({'stare': 'reconciled'})
                    if payment.destination_journal_id.type == 'cash':
                        domain = [('date', '=', payment.payment_date),
                                  ('journal_id', '=', payment.destination_journal_id.id)]
                        detination_statement = self.env['account.bank.statement'].search(domain, limit=1)
                        if not detination_statement:
                            statement_values = {
                                'journal_id': payment.destination_journal_id.id,
                                'date': payment.payment_date,
                                'name': '/'
                            }
                            detination_statement = self.env['account.bank.statement'].create(statement_values)
                        values['statement_id'] = detination_statement.id
                        values['amount'] = payment.amount
                        line = self.env['account.bank.statement.line'].create(values)
                        lines |= line

                payment.reconciliation_statement_line()
