// Anti-Detection JavaScript Injection
// 쿠팡 Bot 탐지 우회를 위한 JavaScript 환경 설정

// Remove webdriver property (CRITICAL!)
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// Profile-based plugin simulation (consistent per profile)
Object.defineProperty(navigator, 'plugins', {
    get: () => Array.from({length: {PLUGIN_COUNT}}, (_, i) => ({
        name: `Plugin_${i}`,
        filename: `plugin${i}.dll`,
        description: `Plugin ${i} Description`
    }))
});

// Hardware simulation from profile
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => {HARDWARE_CORES}
});

// Chrome object
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {}
};

// Enhanced permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Profile-based language settings (consistent per profile)
Object.defineProperty(navigator, 'language', {get: () => '{PRIMARY_LANGUAGE}'});
Object.defineProperty(navigator, 'languages', {get: () => {LANGUAGES}});

// Profile-based timezone (consistent per profile)
Object.defineProperty(Date.prototype, 'getTimezoneOffset', {
    value: function() { return {TIMEZONE_OFFSET}; }
});

// Profile-based screen properties (consistent per profile)
Object.defineProperty(screen, 'colorDepth', {get: () => {COLOR_DEPTH}});
Object.defineProperty(screen, 'pixelDepth', {get: () => {COLOR_DEPTH}});

// Canvas Fingerprint Protection (consistent noise level per profile)
const originalGetContext = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(contextType, ...args) {
    const context = originalGetContext.apply(this, [contextType, ...args]);
    if (contextType === '2d') {
        const originalToDataURL = this.toDataURL;
        this.toDataURL = function(...args) {
            // Add consistent noise based on profile setting
            const imageData = context.getImageData(0, 0, this.width, this.height);
            const noiseLevel = {CANVAS_NOISE_LEVEL}; // Fixed per profile
            for (let i = 0; i < imageData.data.length; i += 4) {
                // Use seed based on pixel position for consistent noise
                const seed = (i / 4) % 1000;
                const noise = (seed * 0.01 * noiseLevel) % noiseLevel - Math.floor(noiseLevel/2);
                imageData.data[i] += Math.floor(noise);     // R
                imageData.data[i + 1] += Math.floor(noise); // G
                imageData.data[i + 2] += Math.floor(noise); // B
            }
            context.putImageData(imageData, 0, 0);
            return originalToDataURL.apply(this, args);
        };
    }
    return context;
};

// WebGL Fingerprint Protection (profile-based values)
const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === this.RENDERER) {
        return '{WEBGL_RENDERER}';
    }
    if (parameter === this.VENDOR) {
        return '{WEBGL_VENDOR}';
    }
    if (parameter === this.VERSION) {
        return '{WEBGL_VERSION}';
    }
    if (parameter === this.SHADING_LANGUAGE_VERSION) {
        return '{WEBGL_SHADER_VERSION}';
    }
    if (parameter === this.UNMASKED_VENDOR_WEBGL) {
        return '{WEBGL_VENDOR}';
    }
    if (parameter === this.UNMASKED_RENDERER_WEBGL) {
        return '{WEBGL_RENDERER}';
    }
    return originalGetParameter.apply(this, [parameter]);
};

// WebGL2 Protection with same profile-based values
if (window.WebGL2RenderingContext) {
    const originalGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === this.RENDERER) {
            return '{WEBGL_RENDERER}';
        }
        if (parameter === this.VENDOR) {
            return '{WEBGL_VENDOR}';
        }
        if (parameter === this.VERSION) {
            return '{WEBGL2_VERSION}';
        }
        if (parameter === this.SHADING_LANGUAGE_VERSION) {
            return '{WEBGL2_SHADER_VERSION}';
        }
        if (parameter === this.UNMASKED_VENDOR_WEBGL) {
            return '{WEBGL_VENDOR}';
        }
        if (parameter === this.UNMASKED_RENDERER_WEBGL) {
            return '{WEBGL_RENDERER}';
        }
        return originalGetParameter2.apply(this, [parameter]);
    };
} 