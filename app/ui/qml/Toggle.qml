import QtQuick
import QtQuick.Controls.Basic

CheckBox {
    id: control
    implicitHeight: 30
    padding: 0
    spacing: 8
    focusPolicy: Qt.StrongFocus
    font.pixelSize: 14
    palette.windowText: Theme.text
    palette.text: Theme.text
    opacity: enabled ? 1 : 0.55
    indicator: Rectangle {
        implicitWidth: 18
        implicitHeight: 18
        y: (control.height - height) / 2
        radius: 4
        color: control.checked ? Theme.accent : Theme.field
        border.color: control.visualFocus ? Theme.text : (control.checked ? Theme.accent : Theme.muted)
        Text { anchors.centerIn: parent; text: control.checked ? "✓" : ""; color: "#102718"; font.bold: true }
    }
    contentItem: Text {
        leftPadding: control.indicator.width + control.spacing
        color: Theme.text
        text: control.text
        font: control.font
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
    }
}
