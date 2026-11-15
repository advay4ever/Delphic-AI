/** Safe local renderer for Delphic science diagrams. */
(function scienceDiagramModule() {
    "use strict";

    const SVG_NS = "http://www.w3.org/2000/svg";
    const ROOT_FIELDS = ["description", "objects", "title", "type", "version"];
    const DIAGRAM_TYPES = new Set([
        "force_diagram", "circuit_diagram", "process_diagram", "labeled_structure",
    ]);
    const OBJECT_FIELDS = {
        box: ["height", "id", "kind", "label", "width", "x", "y"],
        ellipse: ["cx", "cy", "id", "kind", "label", "rx", "ry"],
        circle: ["cx", "cy", "id", "kind", "label", "r"],
        line: ["id", "kind", "x1", "x2", "y1", "y2"],
        arrow: ["id", "kind", "label", "x1", "x2", "y1", "y2"],
        battery: ["height", "id", "kind", "label", "width", "x", "y"],
        resistor: ["height", "id", "kind", "label", "width", "x", "y"],
        label: ["anchor", "id", "kind", "text", "x", "y"],
    };
    const ID_PATTERN = /^[a-z][a-z0-9_-]{0,39}$/;
    const UNSAFE_TEXT_PATTERN = /[<>]|(?:javascript|data)\s*:/i;
    let figureCounter = 0;

    function hasExactFields(value, fields) {
        return Object.keys(value).sort().join("|") === [...fields].sort().join("|");
    }

    function safeText(value, maximum) {
        return typeof value === "string"
            && value.trim().length > 0
            && value.trim().length <= maximum
            && !/[\u0000-\u001f]/.test(value)
            && !UNSAFE_TEXT_PATTERN.test(value);
    }

    function validNumber(value, minimum = 0) {
        return typeof value === "number" && Number.isFinite(value) && value >= minimum && value <= 100;
    }

    function validateSpec(spec) {
        if (!spec || typeof spec !== "object" || Array.isArray(spec)) return null;
        if (!hasExactFields(spec, ROOT_FIELDS)) return null;
        if (spec.version !== 1 || !DIAGRAM_TYPES.has(spec.type)) return null;
        if (!safeText(spec.title, 80) || !safeText(spec.description, 300)) return null;
        if (!Array.isArray(spec.objects) || spec.objects.length < 1 || spec.objects.length > 24) return null;

        const ids = new Set();
        for (const object of spec.objects) {
            if (!object || typeof object !== "object" || Array.isArray(object)) return null;
            const fields = OBJECT_FIELDS[object.kind];
            if (!fields || !hasExactFields(object, fields)) return null;
            if (!ID_PATTERN.test(object.id) || ids.has(object.id)) return null;
            ids.add(object.id);

            for (const field of fields) {
                if (["id", "kind", "label", "text", "anchor"].includes(field)) continue;
                const minimum = ["width", "height", "rx", "ry", "r"].includes(field) ? 1 : 0;
                if (!validNumber(object[field], minimum)) return null;
            }
            if (["box", "battery", "resistor"].includes(object.kind)
                && (object.x + object.width > 100 || object.y + object.height > 100)) return null;
            if (object.kind === "ellipse"
                && (object.cx - object.rx < 0 || object.cx + object.rx > 100
                    || object.cy - object.ry < 0 || object.cy + object.ry > 100)) return null;
            if (object.kind === "circle"
                && (object.cx - object.r < 0 || object.cx + object.r > 100
                    || object.cy - object.r < 0 || object.cy + object.r > 100)) return null;
            if ("label" in object && !safeText(object.label, 50)) return null;
            if ("text" in object && !safeText(object.text, 60)) return null;
            if ("anchor" in object && !["start", "middle", "end"].includes(object.anchor)) return null;
        }
        return JSON.parse(JSON.stringify(spec));
    }

    function svgElement(name, attributes = {}) {
        const element = document.createElementNS(SVG_NS, name);
        Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
        return element;
    }

    function addText(svg, text, x, y, anchor = "middle", className = "science-diagram-label") {
        const element = svgElement("text", { x, y, "text-anchor": anchor, class: className });
        element.textContent = text;
        svg.appendChild(element);
    }

    function addArrow(svg, object, markerId) {
        const line = svgElement("line", {
            x1: object.x1, y1: object.y1, x2: object.x2, y2: object.y2,
            class: "science-diagram-line science-diagram-arrow",
            "marker-end": `url(#${markerId})`,
        });
        svg.appendChild(line);
        const vertical = Math.abs(object.y2 - object.y1) > Math.abs(object.x2 - object.x1);
        const x = (object.x1 + object.x2) / 2 + (vertical ? 3 : 0);
        const y = (object.y1 + object.y2) / 2 + (vertical ? 1 : -3);
        addText(svg, object.label, x, y, vertical ? "start" : "middle", "science-diagram-arrow-label");
    }

    function addBattery(svg, object) {
        const centerX = object.x + object.width / 2;
        const centerY = object.y + object.height / 2;
        svg.append(
            svgElement("line", { x1: object.x, y1: centerY - 5, x2: object.x + object.width, y2: centerY - 5, class: "science-diagram-line science-diagram-battery-long" }),
            svgElement("line", { x1: centerX - object.width * 0.3, y1: centerY + 4, x2: centerX + object.width * 0.3, y2: centerY + 4, class: "science-diagram-line" }),
        );
        addText(svg, object.label, centerX, object.y + object.height + 8);
    }

    function addResistor(svg, object) {
        const points = [];
        const centerY = object.y + object.height / 2;
        const steps = 8;
        for (let index = 0; index <= steps; index += 1) {
            const x = object.x + (object.width * index / steps);
            const y = index === 0 || index === steps
                ? centerY
                : centerY + (index % 2 === 0 ? -object.height / 2 : object.height / 2);
            points.push(`${x},${y}`);
        }
        svg.appendChild(svgElement("polyline", { points: points.join(" "), class: "science-diagram-line science-diagram-resistor" }));
        addText(svg, object.label, object.x + object.width / 2, object.y - 4);
    }

    function drawObject(svg, object, diagramType, markerId) {
        const showShapeLabel = diagramType !== "labeled_structure";
        if (object.kind === "box") {
            svg.appendChild(svgElement("rect", { x: object.x, y: object.y, width: object.width, height: object.height, rx: 2, class: `science-diagram-shape science-diagram-${object.id}` }));
            if (showShapeLabel) addText(svg, object.label, object.x + object.width / 2, object.y + object.height / 2 + 1.5);
        } else if (object.kind === "ellipse") {
            svg.appendChild(svgElement("ellipse", { cx: object.cx, cy: object.cy, rx: object.rx, ry: object.ry, class: `science-diagram-shape science-diagram-${object.id}` }));
            if (showShapeLabel) addText(svg, object.label, object.cx, object.cy + 1.5);
        } else if (object.kind === "circle") {
            svg.appendChild(svgElement("circle", { cx: object.cx, cy: object.cy, r: object.r, class: `science-diagram-shape science-diagram-${object.id}` }));
            if (showShapeLabel) addText(svg, object.label, object.cx, object.cy + 1.5);
        } else if (object.kind === "line") {
            svg.appendChild(svgElement("line", { x1: object.x1, y1: object.y1, x2: object.x2, y2: object.y2, class: "science-diagram-line" }));
        } else if (object.kind === "arrow") {
            addArrow(svg, object, markerId);
        } else if (object.kind === "battery") {
            addBattery(svg, object);
        } else if (object.kind === "resistor") {
            addResistor(svg, object);
        } else if (object.kind === "label") {
            addText(svg, object.text, object.x, object.y, object.anchor, "science-diagram-callout-label");
        }
    }

    function createFigure(untrustedSpec) {
        const spec = validateSpec(untrustedSpec);
        if (!spec) return null;

        const figure = document.createElement("figure");
        figure.className = `science-diagram science-diagram-${spec.type}`;
        figure.tabIndex = 0;
        figure.setAttribute("aria-label", spec.title);

        const heading = document.createElement("h3");
        heading.className = "science-diagram-title";
        heading.textContent = spec.title;

        const svg = svgElement("svg", {
            viewBox: "0 0 100 100",
            role: "img",
            "aria-label": spec.description,
            preserveAspectRatio: "xMidYMid meet",
        });
        figureCounter += 1;
        const markerId = `science-arrowhead-${figureCounter}`;
        const defs = svgElement("defs");
        const marker = svgElement("marker", {
            id: markerId, viewBox: "0 0 10 10", refX: 8, refY: 5,
            markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse",
        });
        marker.appendChild(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "science-diagram-arrowhead" }));
        defs.appendChild(marker);
        svg.appendChild(defs);
        spec.objects.forEach(object => drawObject(svg, object, spec.type, markerId));

        const caption = document.createElement("figcaption");
        caption.textContent = spec.description;
        figure.append(heading, svg, caption);
        return figure;
    }

    function toStaticHtml(spec) {
        const figure = createFigure(spec);
        return figure ? figure.outerHTML : "";
    }

    window.DelphicScienceDiagrams = Object.freeze({ createFigure, toStaticHtml, validateSpec });
    window.dispatchEvent(new CustomEvent("delphic-science-diagrams-ready"));
}());
