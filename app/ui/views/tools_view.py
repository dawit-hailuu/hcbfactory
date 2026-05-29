"""Tools view: backup / restore / worker performance / accounting export / voucher lookup."""
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QGroupBox, QFileDialog, QMessageBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QDateEdit, QFormLayout,
                             QLineEdit, QInputDialog)
from PyQt5.QtCore import Qt, QDate

from app.services import backup_service, report_service, accounting_export_service
from app.ui.voucher_helper import print_voucher
from app.database.db import DB_PATH

BACKUPS = DB_PATH.parent.parent / "backups"
ACCOUNTING = DB_PATH.parent.parent / "exports"


class ToolsView(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self._build()
        self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        try: self.refresh()
        except Exception: pass

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(20,20,20,20); outer.setSpacing(12)

        t = QLabel("Tools")
        t.setObjectName("pagetitle")
        outer.addWidget(t)

        # Backup group
        bg = QGroupBox("Backup & Restore")
        bv = QVBoxLayout(bg)
        bv.addWidget(QLabel(
            "Save a copy of your entire database to a safe location (USB stick, another folder, "
            "the cloud, etc.). Restoring overwrites the current data — always make a fresh "
            "backup before restoring."
        ))
        row = QHBoxLayout()
        bk = QPushButton("💾  Backup Now"); bk.setObjectName("success")
        bk.clicked.connect(self._do_backup)
        rs = QPushButton("⤺  Restore From Backup"); rs.setObjectName("danger")
        rs.clicked.connect(self._do_restore)
        row.addWidget(bk); row.addWidget(rs); row.addStretch()
        bv.addLayout(row)
        outer.addWidget(bg)

        # Voucher lookup group
        vg = QGroupBox("Print Any Voucher")
        vv = QVBoxLayout(vg)
        vv.addWidget(QLabel(
            "Every transaction (sale, payment, expense, purchase, production, waste) "
            "has a unique voucher number you can re-print at any time. "
            "Prefixes: CASH_SALE / CREDIT_SALE · CRV (Receipt) · EV (Expense) · "
            "SRV (Material) · PRODUCTION · WV (Waste)."
        ))
        vrow = QHBoxLayout()
        self.voucher_input = QLineEdit()
        self.voucher_input.setPlaceholderText("Voucher number, e.g. CRV-20260529-0001")
        vrow.addWidget(self.voucher_input, stretch=1)
        vb = QPushButton("🖨  Print Voucher"); vb.clicked.connect(self._lookup_voucher)
        vrow.addWidget(vb)
        vv.addLayout(vrow)
        outer.addWidget(vg)

        # Accounting export group
        ag = QGroupBox("Accounting Export (for Peachtree / Sage 50)")
        av = QVBoxLayout(ag)
        av.addWidget(QLabel(
            "Generate journal CSVs your accountant can import into Peachtree. "
            "Produces 5 files: sales, receipts, expenses, material purchases, waste. "
            "Each entry is fully balanced (debit = credit) with voucher references."
        ))
        arow = QHBoxLayout()
        arow.addWidget(QLabel("From:"))
        self.acc_from = QDateEdit(); self.acc_from.setCalendarPopup(True)
        self.acc_from.setDisplayFormat("yyyy-MM-dd")
        today = datetime.now().date()
        self.acc_from.setDate(QDate(today.year, today.month, 1))
        arow.addWidget(self.acc_from)
        arow.addWidget(QLabel("To:"))
        self.acc_to = QDateEdit(); self.acc_to.setCalendarPopup(True)
        self.acc_to.setDisplayFormat("yyyy-MM-dd"); self.acc_to.setDate(QDate.currentDate())
        arow.addWidget(self.acc_to)
        ab = QPushButton("📊  Export Journals"); ab.setObjectName("success")
        ab.clicked.connect(self._export_accounting)
        arow.addWidget(ab)
        arow.addStretch()
        av.addLayout(arow)
        outer.addWidget(ag)

        # Worker performance group
        wg = QGroupBox("Worker Performance")
        wv = QVBoxLayout(wg)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("From:"))
        self.dfrom = QDateEdit(); self.dfrom.setCalendarPopup(True)
        self.dfrom.setDisplayFormat("yyyy-MM-dd")
        today = datetime.now().date()
        self.dfrom.setDate(QDate(today.year, today.month, 1))
        filter_row.addWidget(self.dfrom)
        filter_row.addWidget(QLabel("To:"))
        self.dto = QDateEdit(); self.dto.setCalendarPopup(True)
        self.dto.setDisplayFormat("yyyy-MM-dd"); self.dto.setDate(QDate.currentDate())
        filter_row.addWidget(self.dto)
        run = QPushButton("Run"); run.clicked.connect(self.refresh)
        filter_row.addWidget(run); filter_row.addStretch()
        wv.addLayout(filter_row)

        self.perf_table = QTableWidget(0, 5)
        self.perf_table.setHorizontalHeaderLabels(
            ["Worker","Category","Quantity","Unit","Runs"])
        self.perf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.perf_table.verticalHeader().setVisible(False)
        self.perf_table.setAlternatingRowColors(True)
        self.perf_table.setEditTriggers(QTableWidget.NoEditTriggers)
        wv.addWidget(self.perf_table)

        self.perf_empty = QLabel("")
        self.perf_empty.setAlignment(Qt.AlignCenter)
        self.perf_empty.setObjectName("emptystate")
        self.perf_empty.hide()
        wv.addWidget(self.perf_empty)
        outer.addWidget(wg, stretch=1)

    def refresh(self):
        df = self.dfrom.date().toString("yyyy-MM-dd")
        dt = self.dto.date().toString("yyyy-MM-dd")
        rows = report_service.worker_performance(df, dt)
        self.perf_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            unit = "pieces" if row["input_unit"] == "piece" else "m²"
            self.perf_table.setItem(r, 0, QTableWidgetItem(row["made_by"]))
            self.perf_table.setItem(r, 1, QTableWidgetItem(row["category"]))
            self.perf_table.setItem(r, 2, QTableWidgetItem(f"{row['total_qty']:.2f}"))
            self.perf_table.setItem(r, 3, QTableWidgetItem(unit))
            self.perf_table.setItem(r, 4, QTableWidgetItem(str(row["runs"])))
        if not rows:
            self.perf_empty.setText(
                f"No production runs in {df} to {dt}, or no 'Made by' worker names recorded yet."
            )
            self.perf_empty.show()
        else:
            self.perf_empty.hide()

    def _do_backup(self):
        default = backup_service.default_backup_path()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Backup", default, "SQLite Database (*.db)"
        )
        if not path: return
        try:
            out = backup_service.make_backup(path)
            QMessageBox.information(self, "Backed up",
                f"Database saved to:\n{out}\n\n"
                f"Keep this file in a safe place — a USB drive or another folder.")
        except PermissionError:
            QMessageBox.critical(self, "Cannot save backup",
                f"Cannot write to:\n{path}\n\n"
                "Choose a different folder, or close any program that has this file open.")
        except Exception as e:
            QMessageBox.critical(self, "Backup failed", str(e))

    def _do_restore(self):
        confirm = QMessageBox.warning(
            self, "Restore database",
            "This will OVERWRITE your current database.\n\n"
            "The current file will be kept as a rescue copy (factory.db.pre-restore), "
            "but you should still make a fresh backup first.\n\n"
            "After restoring, the app will close. Reopen it to use the restored data.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if confirm != QMessageBox.Yes: return

        BACKUPS.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose backup file to restore", str(BACKUPS), "SQLite Database (*.db)"
        )
        if not path: return
        try:
            backup_service.restore_backup(path)
        except Exception as e:
            QMessageBox.critical(self, "Restore failed", str(e))
            return
        QMessageBox.information(
            self, "Restored",
            "Database restored. The app will now close.\n"
            "Reopen it to use the restored data."
        )
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().quit()

    def _lookup_voucher(self):
        vno = self.voucher_input.text().strip().upper()
        if not vno:
            return
        print_voucher(self, vno)

    def _export_accounting(self):
        df = self.acc_from.date().toString("yyyy-MM-dd")
        dt = self.acc_to.date().toString("yyyy-MM-dd")
        if df > dt:
            QMessageBox.warning(self, "Invalid date range",
                "The 'From' date must be on or before the 'To' date."); return
        ACCOUNTING.mkdir(parents=True, exist_ok=True)
        out_dir = QFileDialog.getExistingDirectory(
            self, "Choose folder to save journal files",
            str(ACCOUNTING)
        )
        if not out_dir:
            return
        try:
            files = accounting_export_service.export_period(df, dt, out_dir)
            QMessageBox.information(
                self, "Exported",
                f"Wrote {len(files)} journal files to:\n{out_dir}\n\n" +
                "\n".join(Path(f).name for f in files)
            )
        except PermissionError:
            QMessageBox.critical(self, "Cannot save",
                f"Cannot write to:\n{out_dir}\n\n"
                "Choose a different folder, or close any files that may be open there.")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
