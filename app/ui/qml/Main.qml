import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Rectangle {
    id: root
    width: 480
    height: 720
    color: Theme.canvas
    property int page: 0
    readonly property bool inSession: ["recording", "paused", "pausing", "resuming", "changingMic"].includes(session.phase)
    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 49
            color: Theme.surface
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 0
                Repeater {
                    model: ["Grabar", "Transcripciones", "Ajustes"]
                    delegate: TabButton {
                        id: tab
                        required property int index
                        required property string modelData
                        objectName: "tab" + index
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        focusPolicy: Qt.StrongFocus
                        text: modelData
                        checked: root.page === index
                        onClicked: root.page = index
                        Keys.onRightPressed: { root.page = (index + 1) % 3; tabsFocus(root.page) }
                        Keys.onLeftPressed: { root.page = (index + 2) % 3; tabsFocus(root.page) }
                        function tabsFocus(position) { parent.children[position].forceActiveFocus() }
                        contentItem: Text {
                            text: tab.text
                            font.pixelSize: 14
                            font.weight: tab.checked ? Font.DemiBold : Font.Normal
                            color: tab.checked ? Theme.text : Theme.muted
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        background: Rectangle {
                            color: tab.hovered || tab.visualFocus ? Theme.field : Theme.surface
                            Rectangle {
                                anchors.bottom: parent.bottom
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: Math.min(parent.width - 28, 96)
                                height: 3
                                radius: 1
                                color: tab.checked ? Theme.accent : "transparent"
                            }
                        }
                    }
                }
            }
        }
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: root.page
            RecordingPage {}
            TranscriptionsPage {}
            SettingsPage {}
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: footer.implicitHeight + 20
            color: Theme.surface
            Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }
            ColumnLayout {
                id: footer
                x: 16
                y: 9
                width: parent.width - 32
                spacing: 5
                Text {
                    Layout.fillWidth: true
                    text: desk.statusText
                    color: Theme.muted
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                    Accessible.role: Accessible.StaticText
                    Accessible.name: text
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Caption {
                        objectName: "clock"
                        text: desk.metrics.time
                        font.pixelSize: root.width < 390 ? 18 : 22
                        font.family: Qt.platform.os === "windows" ? "Consolas" : "Menlo"
                        Accessible.name: "Tiempo grabado " + text
                    }
                    Item { Layout.fillWidth: true }
                    ActionButton {
                        objectName: "pauseButton"
                        visible: root.inSession
                        enabled: !session.busy
                        text: session.phase === "paused" || session.phase === "resuming" ? "Reanudar" : "Pausar"
                        onClicked: session.togglePause()
                    }
                    ActionButton {
                        objectName: "recordButton"
                        enabled: !session.busy && (session.phase !== "idle" || (!inputs.busy && picker.labels.length > 0))
                        Layout.preferredWidth: root.width < 390 ? 101 : 128
                        fill: root.inSession || session.phase === "saving" ? Theme.danger : Theme.accent
                        ink: "#102219"
                        text: session.phase === "recovery" ? "Recuperar" : session.phase === "saving" ? "Guardando…"
                             : session.phase === "starting" ? "Iniciando…" : root.inSession ? "Detener" : "Grabar"
                        onClicked: desk.recordAction()
                    }
                }
            }
        }
    }
}
