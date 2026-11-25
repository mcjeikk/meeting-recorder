import QtQuick

Rectangle {
    property real level: 0
    implicitHeight: 5
    radius: 2
    color: Theme.field
    Rectangle {
        height: parent.height
        width: parent.width * Math.min(1, Math.max(0, parent.level))
        radius: 2
        color: Theme.accent
    }
}
