// editor-apprentice — After Effects helpers (ExtendScript / ES3). Run scene scripts with scripts/ae_run.py.
// Either run the scene with `ae_run.py --lib scene.jsx` (this file loads first), or start the scene with:
//   var EA = {folder: "Claude Scenes", w: 1920, h: 1080, fps: 25, font: "<client font>", icons: "<folder of SVGs>",
//             colors: {bg: [30,30,36], text: [255,255,255], accent: [0,160,255]}};
//   eval(readUtf8("<path of this file>"));   // readUtf8 comes from ae_run.py; keep the eval at the top level
// Set EA before loading this file. Non-ASCII text in scene files is fine: ae_run.py reads them as UTF-8.
// Colors, fonts and sizes come from the client's identity (client skill), never from here.
if (typeof EA === "undefined") var EA = {};
var W = EA.w || 1920, H = EA.h || 1080, FPS = EA.fps || 25;
var FONT = EA.font || "Arial";
var FOLDER = EA.folder || "Claude Scenes";
var ICONS = EA.icons || "";
var C = EA.colors || {bg: [30, 30, 36], text: [255, 255, 255], accent: [0, 160, 255], tile: [60, 60, 68]};
function rgb(c) { return [c[0] / 255, c[1] / 255, c[2] / 255]; }

// ---------- reading the editor's project (use before building, and to learn from their final) ----------
function q(s) { return '"' + String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\r?\n|\r/g, "\\n") + '"'; }
function toJSON(v) { // minimal JSON for results (ExtendScript may lack JSON)
    if (v === null || v === undefined) return "null";
    if (typeof v === "number" || typeof v === "boolean") return String(v);
    if (typeof v === "string") return q(v);
    if (v instanceof Array) { var a = []; for (var i = 0; i < v.length; i++) a.push(toJSON(v[i])); return "[" + a.join(",") + "]"; }
    var o = []; for (var k in v) if (v.hasOwnProperty(k)) o.push(q(k) + ":" + toJSON(v[k])); return "{" + o.join(",") + "}";
}
function effectsOf(L) {
    var out = [], fx = L.property("Effects");
    if (!fx) return out;
    for (var i = 1; i <= fx.numProperties; i++) out.push({name: fx.property(i).name, match: fx.property(i).matchName, on: fx.property(i).enabled});
    return out;
}
function inspect(o) { // project summary: comps → layers (type, in/out, parent, effects, text/font, keyframed props)
    o = o || {};
    var comps = [];
    for (var i = 1; i <= app.project.numItems; i++) {
        var c = app.project.item(i);
        if (!(c instanceof CompItem)) continue;
        if (o.only && c.name.indexOf(o.only) < 0) continue;
        var layers = [];
        for (var j = 1; j <= c.numLayers; j++) {
            var L = c.layer(j), e = {i: j, name: L.name, t0: L.inPoint, t1: L.outPoint};  // ES3: "in" can't be a key
            if (L.parent) e.parent = L.parent.name;
            if (L.source) e.source = L.source.name;
            var fx = effectsOf(L); if (fx.length) e.fx = fx;
            try { var td = L.property("Source Text").value; e.text = td.text; e.font = td.font; e.size = td.fontSize; } catch (x) {}
            var keyed = [], tr = L.property("Transform");
            for (var t = 1; tr && t <= tr.numProperties; t++) if (tr.property(t).numKeys > 0) keyed.push(tr.property(t).name + "×" + tr.property(t).numKeys);
            if (keyed.length) e.keys = keyed;
            layers.push(e);
        }
        comps.push({name: c.name, dur: c.duration, w: c.width, h: c.height, fps: c.frameRate,
                    folder: c.parentFolder ? c.parentFolder.name : "", layers: o.layers === false ? c.numLayers : layers});
    }
    return toJSON({project: app.project.file ? app.project.file.fsName : "(unsaved)", comps: comps});
}

// ---------- project items ----------
function folder(name) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof FolderItem && it.name === name) return it;
    }
    return app.project.items.addFolder(name);
}
function newComp(name, dur) { // replaces only a comp of the same name inside OUR folder — never the editor's comps
    var f = folder(FOLDER);
    for (var i = app.project.numItems; i >= 1; i--) {
        var it = app.project.item(i);
        if (it instanceof CompItem && it.name === name && it.parentFolder === f) it.remove();
    }
    var c = app.project.items.addComp(name, W, H, 1, dur, FPS);
    c.parentFolder = f;
    c.bgColor = rgb(C.bg);
    return c;
}
function imp(path) { // import once, reuse
    var f = new File(path);
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof FootageItem && it.file && it.file.fsName === f.fsName) return it;
    }
    var ft = app.project.importFile(new ImportOptions(f));
    ft.parentFolder = folder(FOLDER + " Assets");
    return ft;
}

// ---------- animation ----------
function ez(p) { // ease every keyframe
    var e = new KeyframeEase(0, 75);
    for (var k = 1; k <= p.numKeys; k++) {
        var n = 1;
        var sp = p.propertyValueType === PropertyValueType.TwoD_SPATIAL || p.propertyValueType === PropertyValueType.ThreeD_SPATIAL;
        if (!sp) { var v = p.keyValue(k); n = (v instanceof Array) ? v.length : 1; }
        var a = []; for (var d = 0; d < n; d++) a.push(e);
        try { p.setTemporalEaseAtKey(k, a, a); } catch (x) {}
    }
}
function keys(p, list) { for (var k = 0; k < list.length; k++) p.setValueAtTime(list[k][0], list[k][1]); ez(p); }
function pop(L, t, s) { s = s || 100; keys(L.property("Scale"), [[t, [0, 0]], [t + 0.25, [s * 1.08, s * 1.08]], [t + 0.42, [s, s]]]); }
function fadeIn(L, t, d) { keys(L.property("Opacity"), [[t, 0], [t + (d || 0.4), 100]]); }
function slideIn(L, t, dx, dy) {
    var p = L.property("Position").value;
    keys(L.property("Position"), [[t, [p[0] + dx, p[1] + dy]], [t + 0.5, [p[0], p[1]]]]);
    fadeIn(L, t, 0.35);
}
// Group a card's layers under a null BEFORE animating the null; parenting to a layer that is at scale 0 throws
// the children off.
function nul(comp, name, pos) { var n = comp.layers.addNull(); n.name = name; n.property("Position").setValue(pos); return n; }
function adopt(parent, layers) { for (var i = 0; i < layers.length; i++) layers[i].parent = parent; }

// ---------- layers ----------
function solid(comp, color, name) { // comp.bgColor doesn't render in Premiere/exports — use a real solid
    var s = comp.layers.addSolid(rgb(color), name || "Background", W, H, 1, comp.duration);
    s.moveToEnd();
    return s;
}
function measure(L) { // real text box: the script's sourceRectAtTime() is stale right after styling; the expression engine isn't
    var R = L.property("Rotation"), out = {}, f = ["left", "top", "width", "height"];
    for (var i = 0; i < f.length; i++) {
        R.expression = "sourceRectAtTime(0, false)." + f[i];
        out[f[i]] = R.valueAtTime(0, false);
    }
    R.expression = ""; R.setValue(0);
    return out;
}
function txt(comp, str, size, color, pos, o) {
    // o: {rtl, align: "left"|"right"|"center", maxW, tracking, leading, outline, name, font}
    // Right-to-left text (Arabic, Hebrew, Persian…) is centre-justified and placed by its centre: with many RTL fonts
    // right/left justification doesn't stick, and the measured horizontal box is wrong. Left-to-right text is aligned
    // on its measured box. Set o.rtl for RTL text; LTR words inside an RTL project need direction LTR or they mirror.
    o = o || {};
    var L = comp.layers.addText(str);
    var p = L.property("Source Text"), d = p.value;
    d.font = o.font || FONT; d.fontSize = size;
    if (o.outline) { d.applyFill = false; d.applyStroke = true; d.strokeColor = rgb(color); d.strokeWidth = o.outline; }
    else { d.fillColor = rgb(color); d.applyFill = true; }
    d.justification = ParagraphJustification.CENTER_JUSTIFY;
    if (o.tracking) d.tracking = o.tracking;
    if (o.leading) { d.autoLeading = false; d.leading = o.leading; }
    try { d.direction = o.rtl ? ParagraphDirection.DIRECTION_RIGHT_TO_LEFT : ParagraphDirection.DIRECTION_LEFT_TO_RIGHT; } catch (x) {}
    p.setValue(d);
    var m = measure(L);
    var ax = o.align === "right" ? 1 : o.align === "left" ? 0 : 0.5;
    L.property("Anchor Point").setValue([o.rtl ? 0 : m.left + m.width * ax, m.top + m.height / 2]);
    if (o.maxW && m.width > o.maxW) { var k = o.maxW / m.width * 100; L.property("Scale").setValue([k, k]); }
    L.property("Position").setValue(pos);
    if (o.name) L.name = o.name;
    return L;
}
function rrect(comp, name, size, radius, fill, pos, o) {
    o = o || {};
    var L = comp.layers.addShape(); L.name = name;
    var g = L.property("Contents").addProperty("ADBE Vector Group");
    var r = g.property("Contents").addProperty("ADBE Vector Shape - Rect");
    r.property("Size").setValue(size); r.property("Roundness").setValue(radius);
    if (fill) {
        var f = g.property("Contents").addProperty("ADBE Vector Graphic - Fill");
        f.property("Color").setValue(rgb(fill));
        if (o.fillOpacity !== undefined) f.property("Opacity").setValue(o.fillOpacity);
    }
    if (o.stroke) {
        var s = g.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
        s.property("Color").setValue(rgb(o.strokeColor || C.text)); s.property("Stroke Width").setValue(o.stroke);
    }
    L.property("Position").setValue(pos);
    return L;
}
function line(comp, name, a, b, color, w, t) { // optional draw-on from time t
    var L = comp.layers.addShape(); L.name = name;
    var g = L.property("Contents").addProperty("ADBE Vector Group");
    var sh = new Shape(); sh.vertices = [a, b]; sh.closed = false;
    g.property("Contents").addProperty("ADBE Vector Shape - Group").property("Path").setValue(sh);
    var st = g.property("Contents").addProperty("ADBE Vector Graphic - Stroke");
    st.property("Color").setValue(rgb(color)); st.property("Stroke Width").setValue(w);
    st.property("Line Cap").setValue(2);
    if (t !== undefined && t !== null) keys(g.property("Contents").addProperty("ADBE Vector Filter - Trim").property("End"), [[t, 0], [t + 0.45, 100]]);
    L.property("Anchor Point").setValue([0, 0]); L.property("Position").setValue([0, 0]);
    return L;
}
function icon(comp, file, size, color, pos) {
    // SVG icons import as vector footage; collapse transformations keeps them crisp at any scale; recolor with Fill.
    // Icon sets with permissive licenses (e.g. Tabler, MIT) can be downloaded as SVG; set stroke/fill to white first.
    var L = comp.layers.add(imp(file.indexOf("/") >= 0 || file.indexOf("\\") >= 0 ? file : ICONS + "/" + file + ".svg"));
    var k = size / 24 * 100;
    L.property("Scale").setValue([k, k]);
    try { L.collapseTransformation = true; } catch (e) {}
    L.property("Position").setValue(pos);
    if (color) L.property("Effects").addProperty("ADBE Fill").property("Color").setValue(rgb(color));
    return L;
}
function video(comp, path, pos, scale, matte) { // footage in a (rounded) matte, muted, looping for the comp length
    var L = comp.layers.add(imp(path));
    L.audioEnabled = false;
    if (scale) L.property("Scale").setValue([scale, scale]);
    L.property("Position").setValue(pos);
    try { L.timeRemapEnabled = true; L.property("Time Remap").expression = "loopOut()"; L.outPoint = comp.duration; } catch (e) {}
    if (matte) { L.moveAfter(matte); L.setTrackMatte(matte, TrackMatteType.ALPHA); }
    return L;
}

// ---------- looking at your own work ----------
function snap(comp, times, outDir) { // PNG per time → tile them with scripts/frames.py --sheet
    var dir = new Folder(outDir || EA.out || Folder.temp.fsName + "/ea-snaps");
    if (!dir.exists) dir.create();
    var out = [];
    for (var k = 0; k < times.length; k++) {
        var f = new File(dir.fsName + "/" + comp.name.replace(/[\\\/:*?"<>|]/g, "_") + "_" + k + ".png");
        comp.saveFrameToPng(times[k], f);
        out.push(f.fsName);
    }
    return out;
}
