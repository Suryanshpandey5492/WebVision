const customCSS = `
    ::-webkit-scrollbar {
        width: 10px;
    }
    ::-webkit-scrollbar-track {
        background: #27272a;
    }
    ::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 0.375rem;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #555;
    }
`;

const styleTag = document.createElement("style");
styleTag.textContent = customCSS;

function appendStyleTag() {
    if (document.head) {
        document.head.append(styleTag);
    } else {
        console.error("document.head is null, retrying...");
        setTimeout(appendStyleTag, 100);
    }
}

document.addEventListener("DOMContentLoaded", appendStyleTag);

let labels = [];

window.unmarkPage=function () {
    labels.forEach(label => label.remove());
    labels = [];
}

window.markPage = function () {
    unmarkPage();
    
    const bodyRect = document.body.getBoundingClientRect();
    const vw = Math.max(document.documentElement.clientWidth, window.innerWidth);
    const vh = Math.max(document.documentElement.clientHeight, window.innerHeight);
    const interactiveTags = new Set(["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A", "IFRAME", "VIDEO"]);
    
    let items = Array.from(document.querySelectorAll("*"))
        .map(element => {
            const tagName = element.tagName;
            const rects = [...element.getClientRects()]
                .filter(bb => {
                    const centerX = bb.left + bb.width / 2;
                    const centerY = bb.top + bb.height / 2;
                    const elAtCenter = document.elementFromPoint(centerX, centerY);
                    return elAtCenter === element || element.contains(elAtCenter);
                })
                .map(bb => ({
                    left: Math.max(0, bb.left),
                    top: Math.max(0, bb.top),
                    width: Math.min(vw, bb.right) - Math.max(0, bb.left),
                    height: Math.min(vh, bb.bottom) - Math.max(0, bb.top)
                }))
                .filter(bb => bb.width * bb.height >= 20);

            if (!rects.length) return null;

            const computedStyle = window.getComputedStyle(element);
            const isInteractive = interactiveTags.has(tagName) || element.onclick || computedStyle.cursor === "pointer";
            if (!isInteractive) return null;

            return {
                element,
                rects,
                text: element.textContent.trim().replace(/\s{2,}/g, " "),
                type: tagName.toLowerCase(),
                ariaLabel: element.getAttribute("aria-label") || ""
            };
        })
        .filter(Boolean);

    items = items.filter(item => 
        !items.some(other => other !== item && other.element.contains(item.element))
    );

    function getRandomColor() {
        return `#${Math.floor(Math.random() * 16777215).toString(16).padStart(6, "0")}`;
    }

    items.forEach((item, index) => {
        const borderColor = getRandomColor();

        item.rects.forEach(({ left, top, width, height }) => {
            let newElement = document.createElement("div");
            Object.assign(newElement.style, {
                outline: `2px dashed ${borderColor}`,
                position: "fixed",
                left: `${left}px`,
                top: `${top}px`,
                width: `${width}px`,
                height: `${height}px`,
                pointerEvents: "none",
                boxSizing: "border-box",
                zIndex: 2147483647
            });

            let label = document.createElement("span");
            label.textContent = index;
            Object.assign(label.style, {
                position: "absolute",
                top: "-19px",
                left: "0px",
                background: borderColor,
                color: "white",
                padding: "2px 4px",
                fontSize: "12px",
                borderRadius: "2px"
            });

            newElement.appendChild(label);
            document.body.appendChild(newElement);
            labels.push(newElement);
        });
    });

    return items.flatMap(item =>
        item.rects.map(({ left, top, width, height }) => ({
            x: (left + left + width) / 2,
            y: (top + top + height) / 2,
            type: item.type,
            text: item.text,
            ariaLabel: item.ariaLabel
        }))
    );
};