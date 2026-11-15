import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const graphInstances = new WeakMap();

const themeColors = {
    light: {
        background: 0xf8fafc,
        grid: 0xcbd5e1,
        axes: 0x334155,
        axisX: 0xdc2626,
        axisY: 0x2563eb,
        axisZ: 0x0f766e,
        line: 0x0f766e,
        point: 0x0f766e,
        surface: 0x0f766e,
        surfaceWire: 0x115e59,
        surfaceLow: 0x2563eb,
        surfaceMid: 0x14b8a6,
        surfaceHigh: 0xe11d48,
        secondarySurfaceLow: 0x7c3aed,
        secondarySurfaceMid: 0xf59e0b,
        secondarySurfaceHigh: 0xf97316,
        secondarySurfaceWire: 0x9a3412,
        label: "#0f172a",
    },
    dark: {
        background: 0x171b23,
        grid: 0x394150,
        axes: 0xd6dde8,
        axisX: 0xff7b7b,
        axisY: 0x73a7ff,
        axisZ: 0x63e6be,
        line: 0x63e6be,
        point: 0x63e6be,
        surface: 0x42cfa1,
        surfaceWire: 0x9af3cf,
        surfaceLow: 0x60a5fa,
        surfaceMid: 0x42cfa1,
        surfaceHigh: 0xfb7185,
        secondarySurfaceLow: 0xa78bfa,
        secondarySurfaceMid: 0xfbbf24,
        secondarySurfaceHigh: 0xf97316,
        secondarySurfaceWire: 0xfde68a,
        label: "#edf2f7",
    },
    neon: {
        background: 0x080d1e,
        grid: 0x2b3f72,
        axes: 0xe6f0ff,
        axisX: 0xff6eaa,
        axisY: 0x52e8ff,
        axisZ: 0x4dffbb,
        line: 0x4dffbb,
        point: 0x52e8ff,
        surface: 0x42d5ff,
        surfaceWire: 0xfe74ff,
        surfaceLow: 0x52e8ff,
        surfaceMid: 0x4dffbb,
        surfaceHigh: 0xff6eaa,
        secondarySurfaceLow: 0xff6eaa,
        secondarySurfaceMid: 0xfe74ff,
        secondarySurfaceHigh: 0xffd166,
        secondarySurfaceWire: 0xffd166,
        label: "#f4f8ff",
    },
};

function getColors(theme) {
    return themeColors[theme] || themeColors.dark;
}

function createFallback(container, message) {
    container.replaceChildren();
    const fallback = document.createElement("p");
    fallback.className = "graph-error";
    fallback.textContent = message;
    container.appendChild(fallback);
}

function createResetButton(reset) {
    const button = document.createElement("button");
    button.className = "graph-reset-btn";
    button.type = "button";
    button.textContent = "Reset view";
    button.setAttribute("aria-label", "Reset graph view");
    button.addEventListener("click", reset);
    return button;
}

function createAxisLabels(container, is3d, color) {
    const labels = [
        ["x", "graph-axis-label graph-axis-x"],
        ["y", "graph-axis-label graph-axis-y"],
    ];
    if (is3d) labels.push(["z", "graph-axis-label graph-axis-z"]);

    labels.forEach(([text, className]) => {
        const label = document.createElement("span");
        label.className = className;
        label.textContent = text;
        label.style.color = color;
        label.setAttribute("aria-hidden", "true");
        container.appendChild(label);
    });
}

function niceStepFromRaw(raw) {
    const power = 10 ** Math.floor(Math.log10(raw));
    const scaled = raw / power;
    if (scaled <= 1) return power;
    if (scaled <= 2) return 2 * power;
    if (scaled <= 5) return 5 * power;
    return 10 * power;
}

function niceStep(span) {
    return niceStepFromRaw(Math.max(span, 1) / 10);
}

function niceStepForTickCount(span, tickCount) {
    return niceStepFromRaw(Math.max(span, 1) / Math.max(tickCount, 1));
}

function get2dViewBounds(camera) {
    const halfWidth = (camera.right - camera.left) / (2 * camera.zoom);
    const halfHeight = (camera.top - camera.bottom) / (2 * camera.zoom);
    return {
        xMin: camera.position.x - halfWidth,
        xMax: camera.position.x + halfWidth,
        yMin: camera.position.y - halfHeight,
        yMax: camera.position.y + halfHeight,
    };
}

function disposeObjectResources(object) {
    object.traverse(child => {
        if (child.geometry) child.geometry.dispose();
        if (child.material) {
            const materials = Array.isArray(child.material) ? child.material : [child.material];
            materials.forEach(material => material.dispose());
        }
    });
}

function clearSceneGroup(group) {
    while (group.children.length) {
        const child = group.children[0];
        group.remove(child);
        disposeObjectResources(child);
    }
}

function addLineSegments(group, points, material) {
    if (!points.length) return;
    const geometry = new THREE.BufferGeometry().setFromPoints(
        points.map(point => new THREE.Vector3(...point))
    );
    group.add(new THREE.LineSegments(geometry, material));
}

function tickValues(min, max, step) {
    const first = Math.ceil(min / step - 1e-9);
    const last = Math.floor(max / step + 1e-9);
    const values = [];
    for (let index = first; index <= last && values.length < 40; index += 1) {
        values.push(index * step);
    }
    return values;
}

function formatTick(value, step) {
    const normalized = Math.abs(value) < step / 1000 ? 0 : value;
    const absolute = Math.abs(normalized);
    if (absolute >= 100000 || (absolute > 0 && absolute < 0.0001)) {
        return normalized.toExponential(1).replace(".0e", "e");
    }
    const decimals = step < 1 ? Math.min(6, Math.ceil(-Math.log10(step))) : 0;
    const formatted = normalized.toFixed(decimals);
    return formatted.includes(".")
        ? formatted.replace(/0+$/, "").replace(/\.$/, "")
        : formatted;
}

function addTickLabel(layer, text, className, left, top) {
    const label = document.createElement("span");
    label.className = `graph-tick-label ${className}`;
    label.textContent = text;
    label.style.left = `${left}px`;
    label.style.top = `${top}px`;
    label.setAttribute("aria-hidden", "true");
    layer.appendChild(label);
}

function createDynamic2dGrid(scene, camera, container, colors) {
    const group = new THREE.Group();
    const labelLayer = document.createElement("div");
    labelLayer.className = "graph-tick-labels";
    labelLayer.style.color = colors.label;
    labelLayer.setAttribute("aria-hidden", "true");
    scene.add(group);
    container.appendChild(labelLayer);

    let previousGridKey = "";

    const redrawLines = (bounds, xStep, yStep) => {
        const horizontalPadding = xStep * 1.5;
        const verticalPadding = yStep * 1.5;
        const xValues = tickValues(bounds.xMin - horizontalPadding, bounds.xMax + horizontalPadding, xStep);
        const yValues = tickValues(bounds.yMin - verticalPadding, bounds.yMax + verticalPadding, yStep);
        const gridPoints = [];
        const axisPoints = [];
        const xMin = bounds.xMin - horizontalPadding;
        const xMax = bounds.xMax + horizontalPadding;
        const yMin = bounds.yMin - verticalPadding;
        const yMax = bounds.yMax + verticalPadding;

        xValues.forEach(x => {
            const target = Math.abs(x) < xStep / 100 ? axisPoints : gridPoints;
            target.push([x, yMin, 0], [x, yMax, 0]);
        });
        yValues.forEach(y => {
            const target = Math.abs(y) < yStep / 100 ? axisPoints : gridPoints;
            target.push([xMin, y, 0], [xMax, y, 0]);
        });

        clearSceneGroup(group);
        addLineSegments(
            group,
            gridPoints,
            new THREE.LineBasicMaterial({ color: colors.grid, transparent: true, opacity: 0.75 })
        );
        addLineSegments(group, axisPoints, new THREE.LineBasicMaterial({ color: colors.axes }));
    };

    const redrawLabels = (bounds, xStep, yStep) => {
        const width = Math.max(container.clientWidth, 1);
        const height = Math.max(container.clientHeight, 1);
        const xSpan = bounds.xMax - bounds.xMin;
        const ySpan = bounds.yMax - bounds.yMin;
        const xAxisY = bounds.yMin <= 0 && bounds.yMax >= 0
            ? (bounds.yMax / ySpan) * height
            : height - 22;
        const yAxisX = bounds.xMin <= 0 && bounds.xMax >= 0
            ? (-bounds.xMin / xSpan) * width
            : 4;
        const xLabelTop = Math.min(Math.max(xAxisY + 5, 3), height - 20);
        const yLabelLeft = Math.min(Math.max(yAxisX + 6, 4), width - 48);

        labelLayer.replaceChildren();
        tickValues(bounds.xMin, bounds.xMax, xStep).forEach(value => {
            if (Math.abs(value) < xStep / 1000) return;
            const left = ((value - bounds.xMin) / xSpan) * width;
            addTickLabel(labelLayer, formatTick(value, xStep), "graph-tick-label-x", left, xLabelTop);
        });
        tickValues(bounds.yMin, bounds.yMax, yStep).forEach(value => {
            const top = ((bounds.yMax - value) / ySpan) * height;
            addTickLabel(labelLayer, formatTick(value, yStep), "graph-tick-label-y", yLabelLeft, top);
        });
    };

    return {
        update() {
            const bounds = get2dViewBounds(camera);
            const xStep = niceStep(bounds.xMax - bounds.xMin);
            const yStep = niceStep(bounds.yMax - bounds.yMin);
            const gridKey = [
                xStep,
                yStep,
                Math.floor(bounds.xMin / xStep),
                Math.ceil(bounds.xMax / xStep),
                Math.floor(bounds.yMin / yStep),
                Math.ceil(bounds.yMax / yStep),
            ].join(":");
            if (gridKey !== previousGridKey) {
                redrawLines(bounds, xStep, yStep);
                previousGridKey = gridKey;
            }
            redrawLabels(bounds, xStep, yStep);
        },
        dispose() {
            clearSceneGroup(group);
            labelLayer.remove();
        },
    };
}

function projectToCanvas(point, camera, width, height) {
    const projected = point.clone().project(camera);
    return {
        left: (projected.x * 0.5 + 0.5) * width,
        top: (-projected.y * 0.5 + 0.5) * height,
        isVisible: projected.x >= -1 && projected.x <= 1
            && projected.y >= -1 && projected.y <= 1
            && projected.z >= -1 && projected.z <= 1,
    };
}

function labelsOverlap(first, second) {
    return first.left < second.left + second.width
        && first.left + first.width > second.left
        && first.top < second.top + second.height
        && first.top + first.height > second.top;
}

function createDynamic3dAxisNumbers(container, camera, viewport, colors) {
    const labelLayer = document.createElement("div");
    labelLayer.className = "graph-tick-labels graph-tick-labels-3d";
    labelLayer.style.color = colors.label;
    labelLayer.setAttribute("aria-hidden", "true");
    container.appendChild(labelLayer);

    const { axisX, axisY, axisHeight } = get3dAxisLayout(viewport);
    const axes = [
        {
            key: "x",
            className: "graph-tick-label-3d graph-tick-label-3d-x",
            min: viewport.x_min,
            max: viewport.x_max,
            start: new THREE.Vector3(viewport.x_min, axisHeight, axisY),
            end: new THREE.Vector3(viewport.x_max, axisHeight, axisY),
            pointFor: value => new THREE.Vector3(value, axisHeight, axisY),
            offset: { left: 0, top: 8 },
            endpointOffset: { left: 10, top: 8 },
            color: colors.axisX,
            skipZero: true,
            minimumTicks: 2,
        },
        {
            key: "y",
            className: "graph-tick-label-3d graph-tick-label-3d-y",
            min: viewport.y_min,
            max: viewport.y_max,
            start: new THREE.Vector3(axisX, axisHeight, viewport.y_min),
            end: new THREE.Vector3(axisX, axisHeight, viewport.y_max),
            pointFor: value => new THREE.Vector3(axisX, axisHeight, value),
            offset: { left: 8, top: 0 },
            endpointOffset: { left: 10, top: -8 },
            color: colors.axisY,
            skipZero: true,
            minimumTicks: 2,
        },
        {
            key: "z",
            className: "graph-tick-label-3d graph-tick-label-3d-z",
            min: viewport.z_min,
            max: viewport.z_max,
            start: new THREE.Vector3(axisX, viewport.z_min, axisY),
            end: new THREE.Vector3(axisX, viewport.z_max, axisY),
            pointFor: value => new THREE.Vector3(axisX, value, axisY),
            offset: { left: 8, top: -8 },
            endpointOffset: { left: 10, top: -16 },
            color: colors.axisZ,
            skipZero: false,
            minimumTicks: 4,
        },
    ];

    return {
        update() {
            const width = Math.max(container.clientWidth, 1);
            const height = Math.max(container.clientHeight, 1);
            const candidates = [];

            axes.forEach(axis => {
                const start = projectToCanvas(axis.start, camera, width, height);
                const end = projectToCanvas(axis.end, camera, width, height);
                const axisPixels = Math.hypot(end.left - start.left, end.top - start.top);
                const targetTicks = Math.min(8, Math.max(axis.minimumTicks, axisPixels / 82));
                const step = niceStepForTickCount(axis.max - axis.min, targetTicks);

                tickValues(axis.min, axis.max, step).forEach(value => {
                    if (axis.skipZero && Math.abs(value) < step / 1000) return;
                    const point = projectToCanvas(axis.pointFor(value), camera, width, height);
                    if (!point.isVisible) return;
                    candidates.push({
                        text: formatTick(value, step),
                        className: axis.className,
                        color: colors.label,
                        left: point.left + axis.offset.left,
                        top: point.top + axis.offset.top,
                        priority: 1,
                    });
                });

                if (end.isVisible) {
                    candidates.push({
                        text: axis.key,
                        className: `graph-axis-end-label graph-axis-end-label-${axis.key}`,
                        color: `#${axis.color.toString(16).padStart(6, "0")}`,
                        left: end.left + axis.endpointOffset.left,
                        top: end.top + axis.endpointOffset.top,
                        priority: 3,
                    });
                }
            });

            labelLayer.replaceChildren();
            const occupied = [];
            candidates
                .sort((first, second) => second.priority - first.priority)
                .forEach(candidate => {
                    const widthEstimate = candidate.text.length * (candidate.priority > 1 ? 8 : 6.4) + 6;
                    const heightEstimate = candidate.priority > 1 ? 15 : 12;
                    const bounds = {
                        left: candidate.left - widthEstimate / 2,
                        top: candidate.top - heightEstimate / 2,
                        width: widthEstimate,
                        height: heightEstimate,
                    };
                    const isInside = bounds.left >= 0 && bounds.top >= 0
                        && bounds.left + bounds.width <= width && bounds.top + bounds.height <= height;
                    if (!isInside || occupied.some(placed => labelsOverlap(bounds, placed))) return;

                    const label = document.createElement("span");
                    label.className = `graph-tick-label ${candidate.className}`;
                    label.textContent = candidate.text;
                    label.style.left = `${candidate.left}px`;
                    label.style.top = `${candidate.top}px`;
                    label.style.color = candidate.color;
                    label.setAttribute("aria-hidden", "true");
                    labelLayer.appendChild(label);
                    occupied.push(bounds);
                });
        },
        dispose() {
            labelLayer.remove();
        },
    };
}

function configure2dCamera(camera, viewport, width, height) {
    const xSpan = Math.max(viewport.x_max - viewport.x_min, 1);
    const ySpan = Math.max(viewport.y_max - viewport.y_min, 1);
    const centerX = (viewport.x_min + viewport.x_max) / 2;
    const centerY = (viewport.y_min + viewport.y_max) / 2;
    const aspect = Math.max(width / height, 0.5);
    const visibleHeight = Math.max(ySpan * 1.15, (xSpan * 1.15) / aspect);
    const visibleWidth = visibleHeight * aspect;

    camera.left = -visibleWidth / 2;
    camera.right = visibleWidth / 2;
    camera.top = visibleHeight / 2;
    camera.bottom = -visibleHeight / 2;
    camera.position.set(centerX, centerY, 10);
    camera.zoom = 1;
    camera.updateProjectionMatrix();
    return new THREE.Vector3(centerX, centerY, 0);
}

function resize2dCameraForAspect(camera, width, height) {
    const aspect = Math.max(width / height, 0.5);
    const baseHeight = camera.top - camera.bottom;
    camera.left = -(baseHeight * aspect) / 2;
    camera.right = (baseHeight * aspect) / 2;
    camera.updateProjectionMatrix();
}

function add2dSeries(scene, graphSpec, colors) {
    const series = graphSpec.series || [];
    series.forEach(item => {
        (item.segments || []).forEach(segment => {
            if (segment.length < 2) return;
            const geometry = new THREE.BufferGeometry().setFromPoints(
                segment.map(([x, y]) => new THREE.Vector3(x, y, 0.1))
            );
            scene.add(new THREE.Line(
                geometry,
                new THREE.LineBasicMaterial({ color: colors.line })
            ));
        });
    });

    if (graphSpec.kind === "points_2d" && Array.isArray(graphSpec.points)) {
        const positions = [];
        graphSpec.points.forEach(([x, y]) => positions.push(x, y, 0.2));
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
        scene.add(new THREE.Points(
            geometry,
            new THREE.PointsMaterial({ color: colors.point, size: 10, sizeAttenuation: false })
        ));
    }

    if (Array.isArray(graphSpec.region_positions) && graphSpec.region_positions.length >= 9) {
        const positions = [];
        for (let index = 0; index < graphSpec.region_positions.length; index += 2) {
            positions.push(graphSpec.region_positions[index], graphSpec.region_positions[index + 1], -0.05);
        }
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
        scene.add(new THREE.Mesh(
            geometry,
            new THREE.MeshBasicMaterial({
                color: colors.surfaceMid,
                transparent: true,
                opacity: 0.2,
                depthWrite: false,
                side: THREE.DoubleSide,
            })
        ));
    }

    if (graphSpec.kind === "vector_field_2d" && Array.isArray(graphSpec.vectors)) {
        graphSpec.vectors.forEach(([x, y, dx, dy]) => {
            const direction = new THREE.Vector3(dx, dy, 0);
            const length = direction.length();
            if (!length) return;
            scene.add(new THREE.ArrowHelper(
                direction.normalize(),
                new THREE.Vector3(x, y, 0.12),
                length,
                colors.line,
                Math.min(length * 0.34, 0.32),
                Math.min(length * 0.22, 0.2)
            ));
        });
    }
}

function render2dGraph(container, graphSpec, colors) {
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 100);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    const controls = new OrbitControls(camera, renderer.domElement);
    const viewport = graphSpec.viewport;

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(colors.background, 1);
    renderer.domElement.className = "three-graph-canvas";
    renderer.domElement.setAttribute("aria-label", "Interactive two-dimensional graph");
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.tabIndex = -1;

    controls.enableRotate = false;
    controls.enableDamping = false;
    controls.enablePan = true;
    controls.enableZoom = true;
    controls.zoomToCursor = true;
    controls.minZoom = 0.4;
    controls.maxZoom = 20;
    controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
    controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
    controls.touches.ONE = THREE.TOUCH.PAN;
    controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;

    add2dSeries(scene, graphSpec, colors);

    container.replaceChildren(renderer.domElement);
    const dynamicGrid = createDynamic2dGrid(scene, camera, container, colors);
    createAxisLabels(container, false, colors.label);

    let initialTarget = new THREE.Vector3();
    let hasInitialView = false;
    const render = () => renderer.render(scene, camera);
    const resize = () => {
        const width = Math.max(container.clientWidth, 1);
        const height = Math.max(container.clientHeight, 1);
        renderer.setSize(width, height, false);
        if (!hasInitialView) {
            initialTarget = configure2dCamera(camera, viewport, width, height);
            controls.target.copy(initialTarget);
            hasInitialView = true;
            controls.update();
        } else {
            resize2dCameraForAspect(camera, width, height);
        }
        dynamicGrid.update();
        render();
    };
    const reset = () => {
        const width = Math.max(container.clientWidth, 1);
        const height = Math.max(container.clientHeight, 1);
        initialTarget = configure2dCamera(camera, viewport, width, height);
        controls.target.copy(initialTarget);
        controls.update();
        dynamicGrid.update();
        render();
    };

    container.appendChild(createResetButton(reset));
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    controls.addEventListener("change", () => {
        dynamicGrid.update();
        render();
    });
    resize();

    return { renderer, controls, observer, scene, cleanup: dynamicGrid.dispose };
}

function axisOrigin(min, max) {
    return min <= 0 && max >= 0 ? 0 : (min + max) / 2;
}

function get3dVisualViewport(viewport) {
    return { ...viewport };
}

function get3dAxisLayout(viewport) {
    return {
        axisX: axisOrigin(viewport.x_min, viewport.x_max),
        axisY: axisOrigin(viewport.y_min, viewport.y_max),
        axisHeight: axisOrigin(viewport.z_min, viewport.z_max),
        baseHeight: viewport.z_min,
    };
}

function addAxisArrow(scene, direction, end, span, color) {
    const length = Math.max(Math.min(span * 0.08, 0.72), 0.18);
    const origin = end.clone().addScaledVector(direction, -length);
    scene.add(new THREE.ArrowHelper(direction, origin, length, color, length * 0.62, length * 0.42));
}

function add3dCoordinateFrame(scene, viewport, colors) {
    const { x_min: xMin, x_max: xMax, y_min: yMin, y_max: yMax } = viewport;
    const { axisX, axisY, axisHeight, baseHeight } = get3dAxisLayout(viewport);
    const topHeight = Math.max(viewport.z_max, baseHeight + 1);
    const divisions = 10;
    const xyPlaneLines = [];
    const wallLines = [];
    const frameLines = [];

    for (let index = 0; index <= divisions; index += 1) {
        const fraction = index / divisions;
        const x = xMin + (xMax - xMin) * fraction;
        const y = yMin + (yMax - yMin) * fraction;
        const height = baseHeight + (topHeight - baseHeight) * fraction;

        xyPlaneLines.push([x, axisHeight, yMin], [x, axisHeight, yMax]);
        xyPlaneLines.push([xMin, axisHeight, y], [xMax, axisHeight, y]);

        // Two back walls create a readable 3D box without covering the surface.
        wallLines.push([x, baseHeight, yMin], [x, topHeight, yMin]);
        wallLines.push([xMin, height, yMin], [xMax, height, yMin]);
        wallLines.push([xMin, baseHeight, y], [xMin, topHeight, y]);
        wallLines.push([xMin, height, yMin], [xMin, height, yMax]);
    }

    const bottom = [
        [xMin, baseHeight, yMin],
        [xMax, baseHeight, yMin],
        [xMax, baseHeight, yMax],
        [xMin, baseHeight, yMax],
    ];
    const top = bottom.map(([x, _height, y]) => [x, topHeight, y]);
    for (let index = 0; index < 4; index += 1) {
        const next = (index + 1) % 4;
        frameLines.push(bottom[index], bottom[next], top[index], top[next], bottom[index], top[index]);
    }

    addLineSegments(
        scene,
        xyPlaneLines,
        new THREE.LineBasicMaterial({ color: colors.grid, transparent: true, opacity: 0.62 })
    );
    addLineSegments(
        scene,
        wallLines,
        new THREE.LineBasicMaterial({ color: colors.grid, transparent: true, opacity: 0.3 })
    );
    addLineSegments(
        scene,
        frameLines,
        new THREE.LineBasicMaterial({ color: colors.axes, transparent: true, opacity: 0.68 })
    );
    addLineSegments(
        scene,
        [[xMin, axisHeight, axisY], [xMax, axisHeight, axisY]],
        new THREE.LineBasicMaterial({ color: colors.axisX })
    );
    addLineSegments(
        scene,
        [[axisX, axisHeight, yMin], [axisX, axisHeight, yMax]],
        new THREE.LineBasicMaterial({ color: colors.axisY })
    );
    addLineSegments(
        scene,
        [[axisX, baseHeight, axisY], [axisX, topHeight, axisY]],
        new THREE.LineBasicMaterial({ color: colors.axisZ })
    );

    addAxisArrow(
        scene,
        new THREE.Vector3(1, 0, 0),
        new THREE.Vector3(xMax, axisHeight, axisY),
        xMax - xMin,
        colors.axisX
    );
    addAxisArrow(
        scene,
        new THREE.Vector3(0, 0, 1),
        new THREE.Vector3(axisX, axisHeight, yMax),
        yMax - yMin,
        colors.axisY
    );
    addAxisArrow(
        scene,
        new THREE.Vector3(0, 1, 0),
        new THREE.Vector3(axisX, topHeight, axisY),
        topHeight - baseHeight,
        colors.axisZ
    );
}

function getSurfaceColors(colors, colorIndex = 0) {
    if (colorIndex % 2 === 1) {
        return {
            low: colors.secondarySurfaceLow,
            middle: colors.secondarySurfaceMid,
            high: colors.secondarySurfaceHigh,
            wire: colors.secondarySurfaceWire,
        };
    }
    return {
        low: colors.surfaceLow,
        middle: colors.surfaceMid,
        high: colors.surfaceHigh,
        wire: colors.surfaceWire,
    };
}

function addSurfaceHeightColors(geometry, positions, viewport, surfaceColors) {
    const low = new THREE.Color(surfaceColors.low);
    const middle = new THREE.Color(surfaceColors.middle);
    const high = new THREE.Color(surfaceColors.high);
    const span = Math.max(viewport.z_max - viewport.z_min, 1e-6);
    const vertexColors = [];

    for (let index = 0; index < positions.length; index += 3) {
        const normalized = THREE.MathUtils.clamp((positions[index + 2] - viewport.z_min) / span, 0, 1);
        const color = normalized <= 0.5
            ? low.clone().lerp(middle, normalized * 2)
            : middle.clone().lerp(high, (normalized - 0.5) * 2);
        vertexColors.push(color.r, color.g, color.b);
    }

    geometry.setAttribute("color", new THREE.Float32BufferAttribute(vertexColors, 3));
}

function addSurfaceOverlay(scene, mesh, viewport, surfaceColors) {
    const rows = Number(mesh.rows);
    const columns = Number(mesh.columns);
    const vertexIndices = mesh.vertex_indices;
    const positions = mesh.positions || [];
    const indices = mesh.indices || [];
    if (!Number.isInteger(rows) || !Number.isInteger(columns)
        || !Array.isArray(vertexIndices) || vertexIndices.length !== rows
        || !positions.length || !indices.length) return;

    const connectedEdges = new Set();
    const addEdge = (first, second) => {
        connectedEdges.add(first < second ? `${first}:${second}` : `${second}:${first}`);
    };
    for (let index = 0; index < indices.length; index += 3) {
        addEdge(indices[index], indices[index + 1]);
        addEdge(indices[index + 1], indices[index + 2]);
        addEdge(indices[index + 2], indices[index]);
    }
    const sharesEdge = (first, second) => {
        if (!Number.isInteger(first) || !Number.isInteger(second)) return false;
        const edge = first < second ? `${first}:${second}` : `${second}:${first}`;
        return connectedEdges.has(edge);
    };
    const pointFor = vertexIndex => {
        const start = vertexIndex * 3;
        return [positions[start], positions[start + 2], positions[start + 1]];
    };
    const surfaceLines = [];
    const addLine = (first, second) => {
        if (!sharesEdge(first, second)) return;
        surfaceLines.push(pointFor(first), pointFor(second));
    };
    const stride = Math.max(1, Math.ceil(Math.max(rows, columns) / 9));
    const selectedRows = new Set([0, rows - 1]);
    const selectedColumns = new Set([0, columns - 1]);
    for (let row = 0; row < rows; row += stride) selectedRows.add(row);
    for (let column = 0; column < columns; column += stride) selectedColumns.add(column);

    selectedRows.forEach(row => {
        const rowIndices = vertexIndices[row];
        if (!Array.isArray(rowIndices) || rowIndices.length !== columns) return;
        for (let column = 0; column < columns - 1; column += 1) {
            addLine(rowIndices[column], rowIndices[column + 1]);
        }
    });
    selectedColumns.forEach(column => {
        for (let row = 0; row < rows - 1; row += 1) {
            addLine(vertexIndices[row]?.[column], vertexIndices[row + 1]?.[column]);
        }
    });

    addLineSegments(
        scene,
        surfaceLines,
        new THREE.LineBasicMaterial({
            color: surfaceColors.wire,
            transparent: true,
            opacity: 0.7,
            clippingPlanes: [
                new THREE.Plane(new THREE.Vector3(0, 1, 0), -viewport.z_min),
                new THREE.Plane(new THREE.Vector3(0, -1, 0), viewport.z_max),
            ],
        })
    );
}

function add3dSurface(scene, surface, viewport, colors) {
    const positions = surface.mesh?.positions || [];
    const indices = surface.mesh?.indices || [];
    const mappedPositions = [];

    for (let index = 0; index < positions.length; index += 3) {
        const x = positions[index];
        const y = positions[index + 1];
        const z = positions[index + 2];
        mappedPositions.push(x, z, y);
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(mappedPositions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    const surfaceColors = getSurfaceColors(colors, Number(surface.color_index) || 0);
    addSurfaceHeightColors(geometry, positions, viewport, surfaceColors);

    const material = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        roughness: 0.38,
        metalness: 0.08,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.8,
        vertexColors: true,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
        clippingPlanes: [
            new THREE.Plane(new THREE.Vector3(0, 1, 0), -viewport.z_min),
            new THREE.Plane(new THREE.Vector3(0, -1, 0), viewport.z_max),
        ],
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.userData.surfaceLabel = surface.raw_expression || "Surface";
    scene.add(mesh);
    addSurfaceOverlay(scene, surface.mesh || {}, viewport, surfaceColors);
    return mesh;
}

function add3dCurves(scene, curves, colors) {
    if (!Array.isArray(curves)) return;
    curves.forEach(curve => {
        if (!Array.isArray(curve.points) || curve.points.length < 2) return;
        const points = curve.points.map(([x, y, z]) => new THREE.Vector3(x, z, y));
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        scene.add(new THREE.Line(
            geometry,
            new THREE.LineBasicMaterial({ color: colors.point, transparent: true, opacity: 0.96 })
        ));
    });
}

function add3dScene(scene, graphSpec, colors) {
    const viewport = get3dVisualViewport(graphSpec.viewport);
    const surfaces = Array.isArray(graphSpec.surfaces) && graphSpec.surfaces.length
        ? graphSpec.surfaces
        : graphSpec.mesh ? [{
            mesh: graphSpec.mesh,
            raw_expression: graphSpec.raw_expression,
            color_index: 0,
        }] : [];

    add3dCoordinateFrame(scene, viewport, colors);
    const meshes = surfaces.map(surface => add3dSurface(scene, surface, viewport, colors));
    add3dCurves(scene, graphSpec.curves, colors);

    scene.add(new THREE.HemisphereLight(0xffffff, colors.background, 1.55));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.55);
    keyLight.position.set(8, 14, 10);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(colors.surfaceWire, 0.4);
    fillLight.position.set(-9, 5, -7);
    scene.add(fillLight);

    return meshes;
}

function prefersReducedMotion() {
    return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

function get3dViewState(view, viewport) {
    const xCenter = (viewport.x_min + viewport.x_max) / 2;
    const yCenter = (viewport.y_min + viewport.y_max) / 2;
    const zCenter = (viewport.z_min + viewport.z_max) / 2;
    const span = Math.max(
        viewport.x_max - viewport.x_min,
        viewport.y_max - viewport.y_min,
        viewport.z_max - viewport.z_min,
        4
    );
    const target = new THREE.Vector3(xCenter, zCenter, yCenter);
    const distance = span * 1.8;

    if (view === "top") {
        return {
            position: new THREE.Vector3(xCenter, zCenter + distance, yCenter),
            target,
            up: new THREE.Vector3(0, 0, -1),
        };
    }
    if (view === "front") {
        return {
            position: new THREE.Vector3(xCenter, zCenter, yCenter + distance),
            target,
            up: new THREE.Vector3(0, 1, 0),
        };
    }
    if (view === "side") {
        return {
            position: new THREE.Vector3(xCenter + distance, zCenter, yCenter),
            target,
            up: new THREE.Vector3(0, 1, 0),
        };
    }
    return {
        position: new THREE.Vector3(
            xCenter + span * 1.08,
            zCenter + span * 0.92,
            yCenter + span * 1.08
        ),
        target,
        up: new THREE.Vector3(0, 1, 0),
    };
}

function createCameraAnimator(camera, controls, render) {
    let frameId = null;
    let isAnimating = false;

    const cancel = () => {
        if (frameId !== null) window.cancelAnimationFrame(frameId);
        frameId = null;
        isAnimating = false;
    };
    const moveTo = state => {
        cancel();
        isAnimating = true;
        const apply = progress => {
            camera.position.lerpVectors(startPosition, state.position, progress);
            controls.target.lerpVectors(startTarget, state.target, progress);
            camera.up.lerpVectors(startUp, state.up, progress).normalize();
            camera.updateProjectionMatrix();
            controls.update();
            render();
        };
        const startPosition = camera.position.clone();
        const startTarget = controls.target.clone();
        const startUp = camera.up.clone();

        if (prefersReducedMotion()) {
            apply(1);
            isAnimating = false;
            return;
        }

        const startedAt = performance.now();
        const duration = 180;
        const step = now => {
            const progress = Math.min((now - startedAt) / duration, 1);
            const eased = 1 - (1 - progress) ** 3;
            apply(eased);
            if (progress < 1) {
                frameId = window.requestAnimationFrame(step);
            } else {
                frameId = null;
                isAnimating = false;
            }
        };
        frameId = window.requestAnimationFrame(step);
    };

    return { cancel, isAnimating: () => isAnimating, moveTo };
}

function create3dViewToolbar(container, onView, onReset) {
    const toolbar = document.createElement("div");
    toolbar.className = "graph-view-toolbar";
    toolbar.setAttribute("role", "toolbar");
    toolbar.setAttribute("aria-label", "Three-dimensional graph views");
    const buttons = new Map();
    const views = [
        ["default", "3D", "Use the default three-dimensional view"],
        ["top", "Top", "Look down at the x-y plane"],
        ["front", "Front", "Look at the graph from the front"],
        ["side", "Side", "Look at the graph from the side"],
    ];

    views.forEach(([view, label, description]) => {
        const button = document.createElement("button");
        button.className = "graph-view-btn";
        button.type = "button";
        button.textContent = label;
        button.title = description;
        button.setAttribute("aria-label", description);
        button.setAttribute("aria-pressed", "false");
        button.addEventListener("click", () => onView(view));
        toolbar.appendChild(button);
        buttons.set(view, button);
    });

    const resetButton = document.createElement("button");
    resetButton.className = "graph-view-btn graph-view-reset-btn";
    resetButton.type = "button";
    resetButton.textContent = "Reset";
    resetButton.title = "Restore this view's original framing";
    resetButton.setAttribute("aria-label", "Reset the current graph view");
    resetButton.addEventListener("click", onReset);
    toolbar.appendChild(resetButton);
    container.appendChild(toolbar);

    return {
        setActive(view) {
            buttons.forEach((button, key) => {
                const selected = key === view;
                button.classList.toggle("is-selected", selected);
                button.setAttribute("aria-pressed", String(selected));
            });
            toolbar.dataset.view = view;
        },
        dispose() {
            toolbar.remove();
        },
    };
}

function formatCoordinate(value) {
    const normalized = Math.abs(value) < 0.005 ? 0 : value;
    const decimals = Math.abs(normalized) >= 10 ? 1 : 2;
    return normalized.toFixed(decimals).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}

function createSurfaceInspector(container, canvas, camera, surfaces, controls) {
    const tooltip = document.createElement("div");
    tooltip.className = "graph-surface-inspector";
    tooltip.hidden = true;
    tooltip.setAttribute("aria-hidden", "true");
    container.appendChild(tooltip);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let pointerDown = null;
    let isDragging = false;

    const hide = () => {
        tooltip.hidden = true;
    };
    const inspect = (clientX, clientY) => {
        const bounds = canvas.getBoundingClientRect();
        if (!bounds.width || !bounds.height) return hide();
        pointer.x = ((clientX - bounds.left) / bounds.width) * 2 - 1;
        pointer.y = -((clientY - bounds.top) / bounds.height) * 2 + 1;
        raycaster.setFromCamera(pointer, camera);
        const hit = raycaster.intersectObjects(surfaces, false)[0];
        if (!hit) return hide();

        const { x, y: z, z: mathY } = hit.point;
        tooltip.textContent = `x = ${formatCoordinate(x)}, y = ${formatCoordinate(mathY)}, z = ${formatCoordinate(z)}`;
        tooltip.style.left = `${THREE.MathUtils.clamp(clientX - bounds.left + 12, 8, bounds.width - 164)}px`;
        tooltip.style.top = `${THREE.MathUtils.clamp(clientY - bounds.top + 12, 8, bounds.height - 34)}px`;
        tooltip.hidden = false;
    };
    const onPointerDown = event => {
        pointerDown = { id: event.pointerId, x: event.clientX, y: event.clientY, time: performance.now(), moved: false };
    };
    const onPointerMove = event => {
        if (pointerDown?.id === event.pointerId
            && Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y) > 8) {
            pointerDown.moved = true;
        }
        if (event.pointerType === "mouse" && !isDragging && event.buttons === 0) {
            inspect(event.clientX, event.clientY);
        }
    };
    const onPointerUp = event => {
        if (event.pointerType === "touch" && pointerDown?.id === event.pointerId) {
            const elapsed = performance.now() - pointerDown.time;
            if (!pointerDown.moved && elapsed <= 300) inspect(event.clientX, event.clientY);
        }
        pointerDown = null;
    };
    const onControlStart = () => {
        isDragging = true;
        hide();
    };
    const onControlEnd = () => {
        isDragging = false;
    };

    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerup", onPointerUp);
    const onPointerLeave = event => {
        if (event.pointerType === "mouse") hide();
    };
    canvas.addEventListener("pointerleave", onPointerLeave);
    controls.addEventListener("start", onControlStart);
    controls.addEventListener("end", onControlEnd);

    return {
        dispose() {
            canvas.removeEventListener("pointerdown", onPointerDown);
            canvas.removeEventListener("pointermove", onPointerMove);
            canvas.removeEventListener("pointerup", onPointerUp);
            canvas.removeEventListener("pointerleave", onPointerLeave);
            controls.removeEventListener("start", onControlStart);
            controls.removeEventListener("end", onControlEnd);
            tooltip.remove();
        },
        hide,
    };
}

function render3dGraph(container, graphSpec, colors) {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 2000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    const controls = new OrbitControls(camera, renderer.domElement);
    const viewport = get3dVisualViewport(graphSpec.viewport);

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(colors.background, 1);
    renderer.localClippingEnabled = true;
    renderer.domElement.className = "three-graph-canvas";
    renderer.domElement.setAttribute("aria-label", "Interactive three-dimensional surface graph");
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.tabIndex = -1;

    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 2;
    controls.maxDistance = 300;
    const surfaces = add3dScene(scene, graphSpec, colors);

    container.replaceChildren(renderer.domElement);
    const dynamicAxisNumbers = createDynamic3dAxisNumbers(container, camera, viewport, colors);
    let activeView = "default";
    let toolbar;
    const render = () => {
        dynamicAxisNumbers.update();
        renderer.render(scene, camera);
    };
    const animator = createCameraAnimator(camera, controls, render);
    const applyView = view => {
        activeView = view;
        toolbar.setActive(view);
        animator.moveTo(get3dViewState(view, viewport));
    };
    const reset = () => applyView(activeView === "custom" ? "default" : activeView);
    toolbar = create3dViewToolbar(container, applyView, reset);
    const inspector = surfaces.length
        ? createSurfaceInspector(container, renderer.domElement, camera, surfaces, controls)
        : null;

    const resize = () => {
        const width = Math.max(container.clientWidth, 1);
        const height = Math.max(container.clientHeight, 1);
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        render();
    };
    const onControlsChange = () => {
        render();
        if (!animator.isAnimating() && activeView !== "custom") {
            activeView = "custom";
            toolbar.setActive("custom");
        }
    };
    const onControlStart = () => animator.cancel();

    const observer = new ResizeObserver(resize);
    observer.observe(container);
    controls.addEventListener("change", onControlsChange);
    controls.addEventListener("start", onControlStart);
    applyView("default");
    resize();

    return {
        renderer,
        controls,
        observer,
        scene,
        cleanup: () => {
            animator.cancel();
            inspector?.dispose();
            toolbar.dispose();
            dynamicAxisNumbers.dispose();
            controls.removeEventListener("change", onControlsChange);
            controls.removeEventListener("start", onControlStart);
        },
    };
}

export function disposeGraph(container) {
    const instance = graphInstances.get(container);
    if (!instance) return;

    instance.observer.disconnect();
    instance.controls.dispose();
    instance.cleanup?.();
    instance.scene.traverse(object => {
        if (object.geometry) object.geometry.dispose();
        if (object.material) {
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            materials.forEach(material => material.dispose());
        }
    });
    instance.renderer.dispose();
    instance.renderer.forceContextLoss();
    graphInstances.delete(container);
}

export function disposeAllGraphs(root = document) {
    root.querySelectorAll(".local-graph-container").forEach(container => disposeGraph(container));
}

export function renderGraph(container, graphSpec, theme) {
    disposeGraph(container);

    if (!window.WebGLRenderingContext) {
        createFallback(container, "Your equation is shown above, but this browser cannot display an interactive graph.");
        return;
    }

    try {
        const colors = getColors(theme);
        const instance = graphSpec.kind === "surface_3d" || graphSpec.kind === "curve_3d"
            ? render3dGraph(container, graphSpec, colors)
            : render2dGraph(container, graphSpec, colors);
        graphInstances.set(container, instance);
    } catch (error) {
        console.error("[GRAPH] Could not render local graph:", error);
        createFallback(container, "Your equation is shown above, but the interactive graph could not be displayed.");
    }
}

window.DelphicGraphing = { disposeAllGraphs, disposeGraph, renderGraph };
window.dispatchEvent(new Event("delphic-graphing-ready"));
