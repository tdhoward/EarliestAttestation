// Minimal offline DOM surface for exercising the real renderer and its text.
// No browser, timers, layout engine, or server is involved.
function explorerDOM() {
  class Node {
    constructor(tag) {
      this.tag = tag; this.children = []; this.attributes = {}; this.listeners = {};
      this.style = {}; this.textContent = ""; this.hidden = false; this.open = false;
      this.clientWidth = 900; this.clientHeight = 320; this.offsetWidth = 100; this.scrollLeft = 0;
    }
    append(...items) {this.children.push(...items);}
    appendChild(item) {this.append(item); return item;}
    replaceChildren(...items) {this.children = items;}
    setAttribute(name, value) {this.attributes[name] = value;}
    addEventListener(name, fn) {(this.listeners[name] ||= []).push(fn);}
    dispatch(name) {for (const listener of this.listeners[name] || []) listener({preventDefault() {}});}
    getContext() {return context;}
  }
  const context = new Proxy({measureText: text => ({width: text.length * 6})}, {
    get(target, name) {return target[name] || (() => {});}
  });
  let draw;
  const view = {AbortController, devicePixelRatio: 1,
    requestAnimationFrame(fn) {draw = fn; return 1;}, cancelAnimationFrame() {},
    ResizeObserver: class {observe() {} disconnect() {}}};
  const nodes = new Map();
  const doc = {defaultView: view, createElement: tag => new Node(tag)};
  const root = {ownerDocument: doc, querySelector(selector) {
    const name = selector.match(/data-el="([^"]+)"/)[1];
    if (!nodes.has(name)) nodes.set(name, new Node(name));
    return nodes.get(name);
  }, querySelectorAll() {return [];}};
  const snapshot = item => ({tag: item.tag, text: item.textContent, href: item.href,
    children: item.children.map(snapshot)});
  const text = item => [item.textContent, ...item.children.map(text)].join("\n");
  return {root, nodes, snapshot, text, draw() {draw?.();}};
}

module.exports = {explorerDOM};
