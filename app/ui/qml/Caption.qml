import QtQuick

Text {
    property bool secondary: false
    color: secondary ? Theme.muted : Theme.text
    font.pixelSize: secondary ? 12 : 14
    font.weight: secondary ? Font.Normal : Font.DemiBold
    wrapMode: Text.WordWrap
}
