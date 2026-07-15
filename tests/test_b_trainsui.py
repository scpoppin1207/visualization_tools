import os
os.environ["ETS_TOOLKIT"] = "qt"
os.environ["QT_API"] = "pyqt5"

from traits.api import HasTraits, Str
from traitsui.api import View, Item

class Person(HasTraits):
    name = Str()
    traits_view = View(Item("name"))

p = Person(name="ChatGPT")
p.configure_traits()