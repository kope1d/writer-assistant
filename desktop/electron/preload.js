"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopBridge", {
  isDesktop: true,
  getWriteToken: () => ipcRenderer.invoke("get-write-token"),
  minimize: () => ipcRenderer.send("window-minimize"),
  toggleMaximize: () => ipcRenderer.send("window-maximize-toggle"),
  close: () => ipcRenderer.send("window-close"),
  onMaximizedChange: (callback) => {
    ipcRenderer.on("window-maximized-changed", (_event, maximized) => {
      callback(maximized);
    });
  },
  onWindowFocus: (callback) => {
    ipcRenderer.on("window-focus-changed", (_event, focused) => {
      callback(focused);
    });
  },
});
