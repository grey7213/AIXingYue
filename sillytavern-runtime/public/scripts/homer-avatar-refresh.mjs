// Changing src cancels a thumbnail that is still being read. Let that exact
// request settle before asking for the uploaded pixels; this is presentation
// refresh only, never a reason to skip the actual first/revised cover upload.
export function refreshSettledAvatarImages(images, { avatar, stamp, baseUrl, isCurrent }) {
    const encodedAvatar = encodeURIComponent(avatar);
    for (const image of images) {
        const source = String(image.getAttribute('src') || '');
        if (!source.includes(encodedAvatar) && !source.includes(avatar)) continue;
        const refresh = () => {
            if (!image.isConnected || String(image.getAttribute('src') || '') !== source || !isCurrent()) return;
            let target;
            try { target = new URL(source, baseUrl); } catch { return; }
            target.searchParams.set('homer_cover', String(stamp));
            image.src = target.href;
        };
        if (image.complete) {
            refresh();
            continue;
        }
        const settled = () => {
            image.removeEventListener('load', settled);
            image.removeEventListener('error', settled);
            refresh();
        };
        image.addEventListener('load', settled, { once: true });
        image.addEventListener('error', settled, { once: true });
    }
}
