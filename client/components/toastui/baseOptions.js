import router from "../../router.js";

const customHTMLRenderer = {
  // Add id attribute to headings
  heading(node, { entering, getChildrenText, origin }) {
    const original = origin();
    if (entering) {
      original.attributes = {
        id: getChildrenText(node)
          .toLowerCase()
          .replace(/[^a-z0-9-\s]*/g, "")
          .trim()
          .replace(/\s/g, "-"),
      };
    }
    return original;
  },
  // Convert relative hash links to absolute links
  link(_, { entering, origin }) {
    const original = origin();
    if (entering) {
      const href = original.attributes.href;
      if (href.startsWith("#")) {
        const targetRoute = {
          ...router.currentRoute.value,
          hash: href,
        };
        original.attributes.href = router.resolve(targetRoute).href;
      }
    }
    return original;
  },
};

const baseOptions = {
  height: "100%",
  plugins: [],
  customHTMLRenderer: customHTMLRenderer,
  useDefaultHTMLSanitizer: true,
  usageStatistics: false,
};

let codeSyntaxHighlightModule = null;
let codeSyntaxHighlightStylesLoaded = false;

async function loadCodeSyntaxHighlight() {
  if (!codeSyntaxHighlightModule) {
    const [pluginModule] = await Promise.all([
      import(
        "@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight-all.js"
      ),
      loadCodeSyntaxHighlightStyles(),
    ]);
    codeSyntaxHighlightModule = pluginModule.default;
  }
  return codeSyntaxHighlightModule;
}

async function loadCodeSyntaxHighlightStyles() {
  if (codeSyntaxHighlightStylesLoaded) {
    return;
  }
  await Promise.all([
    import("prismjs/themes/prism.css"),
    import(
      "@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css"
    ),
  ]);
  codeSyntaxHighlightStylesLoaded = true;
}

export function markdownContainsCodeBlock(markdown) {
  return /(^|\n)(```|~~~)/.test(markdown || "");
}

export async function buildBaseOptions({ codeSyntaxHighlight = false } = {}) {
  if (!codeSyntaxHighlight) {
    return { ...baseOptions };
  }

  return {
    ...baseOptions,
    plugins: [await loadCodeSyntaxHighlight()],
  };
}

export default baseOptions;
