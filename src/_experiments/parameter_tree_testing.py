from PyQt6.QtWidgets import QStyleFactory

if __name__ == '__main__':
    from pyqtgraph.Qt import QtWidgets
    import pyqtgraph as pg
    from pyqtgraph.parametertree import Parameter, ParameterTree, interact


    def a(x=4, y=6, z=False, t="null", f=[]):
        QtWidgets.QMessageBox.information(None, 'Hello World', f'X is {x}, Y is {y}')


    # One line of code, no name/value duplication
    params = interact(a)

    app = pg.mkQApp()
    tree = ParameterTree()
    tree.setParameters(params)
    tree.show()
    pg.exec()