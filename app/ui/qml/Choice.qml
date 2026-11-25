import QtQuick
import QtQuick.Controls.Basic

ComboBox {
    id: control
    property string caption
    Accessible.name: caption
    implicitWidth: 150
    implicitHeight: 38
    focusPolicy: Qt.StrongFocus
    wheelEnabled: activeFocus
    leftPadding: 12
    rightPadding: 32
    opacity: enabled ? 1 : 0.55
    font.pixelSize: 14
    palette.text: Theme.text
    palette.buttonText: Theme.text
    palette.window: Theme.surface
    palette.base: Theme.surface
    palette.highlight: Theme.field
    palette.highlightedText: Theme.text
    background: Rectangle {
        color: control.hovered ? Theme.hover : Theme.field
        border.color: control.visualFocus ? Theme.accent : Theme.line
        radius: 6
    }
    contentItem: Text {
        text: control.displayText
        elide: Text.ElideRight
        color: Theme.text
        font: control.font
        verticalAlignment: Text.AlignVCenter
    }
    indicator: Text {
        x: control.width - width - 12
        anchors.verticalCenter: parent.verticalCenter
        text: "▾"
        color: Theme.muted
    }
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Down && (event.modifiers & Qt.AltModifier)) {
            popup.open()
            event.accepted = true
        }
    }
}
