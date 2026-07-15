from PyQt5.QtWidgets import QApplication, QLabel
import sys

app = QApplication(sys.argv)
label = QLabel("Hello from Qt")
label.show()
app.exec_()