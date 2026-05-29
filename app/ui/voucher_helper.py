"""Tiny helper used by every view to save a voucher PDF via file dialog."""
from PyQt5.QtWidgets import QFileDialog, QMessageBox

from app.services import voucher_pdf_service
from app.utils.paths import VOUCHERS


def print_voucher(parent, voucher_no: str):
    """Open Save dialog and write the voucher PDF.  No-op on cancel."""
    if not voucher_no:
        QMessageBox.warning(parent, "No voucher", "This record has no voucher number.")
        return
    VOUCHERS.mkdir(parents=True, exist_ok=True)
    out = VOUCHERS / f"{voucher_no}.pdf"
    path, _ = QFileDialog.getSaveFileName(
        parent, "Save voucher", str(out), "PDF Files (*.pdf)")
    if not path:
        return
    try:
        voucher_pdf_service.export_voucher(voucher_no, path)
        QMessageBox.information(parent, "Voucher saved", f"Saved to:\n{path}")
    except ValueError as e:
        # Unknown voucher number — friendly message
        QMessageBox.warning(parent, "Voucher not found",
                            f"No record found for voucher '{voucher_no}'.\n"
                            "Double-check the prefix (SV / RV / EV / PV / WV / MV) and number.")
    except PermissionError:
        QMessageBox.critical(parent, "Cannot save",
            f"Cannot write to:\n{path}\n\n"
            "The file may be open in another program. Close it and try again.")
    except Exception as e:
        QMessageBox.critical(parent, "Error", str(e))
