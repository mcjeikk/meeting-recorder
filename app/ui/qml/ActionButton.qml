import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property color fill: Theme.field
    property color ink: Theme.text
    implicitHeight: 38
    leftPadding: 13
    rightPadding: 13
    opacity: enabled ? 1 : 0.52
    Accessible.name: text
    background: Rectangle {
        radius: 7
        color: control.down ? Qt.darker(control.fill, 1.22)
              : control.hovered ? Qt.lighter(control.fill, 1.10) : control.fill
        border.color: control.visualFocus ? Theme.text : "transparent"
        border.width: 2
    }
    contentItem: Text {
        text: control.text
        color: control.ink
        font.pixelSize: 14
        font.weight: Font.DemiBold
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
    }
}
