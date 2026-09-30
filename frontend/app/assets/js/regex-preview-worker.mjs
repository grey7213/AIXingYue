self.onmessage = ({ data }) => {
    try {
        let output = String(data.sample || '').slice(0, 32768);
        let applied = 0;
        for (const rule of data.rules || []) {
            if (rule.disabled || rule.enabled === false) continue;
            let pattern = String(rule.findRegex ?? rule.find ?? ''), flags = String(rule.flags || '');
            const literal = /^\/([\s\S]*)\/([dgimsuvy]*)$/.exec(pattern);
            if (literal) { pattern = literal[1]; flags = literal[2]; }
            const regex = new RegExp(pattern, flags);
            const replacement = String(rule.replaceString ?? rule.replace ?? '').replace(/{{match}}/gi, () => '$&');
            output = output.replace(regex, replacement);
            if (output.length > 2 * 1024 * 1024) throw Error('预览结果过大，请缩短样本文本');
            applied++;
        }
        self.postMessage({ output, applied });
    } catch (error) { self.postMessage({ error: error.message || '正则表达式无效' }); }
};
