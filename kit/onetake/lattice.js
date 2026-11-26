function drawCameraLattice(cameraPose, ink) {
    document.querySelector('#world').style.transform = 'matrix(' + OM.view(cameraPose).join(',') + ')';
    const ctx = document.querySelector('#dots').getContext('2d'), grid = OM.lattice(cameraPose, { depth: 1.35, spacing: 48, px: 1.45 });
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, 1920, 1080);
    ctx.setTransform(...grid.matrix);
    ctx.fillStyle = ink;
    ctx.beginPath();
    for (let x = grid.x0; x < grid.x1; x += grid.spacing)
        for (let y = grid.y0; y < grid.y1; y += grid.spacing) {
            ctx.moveTo(x + grid.r, y);
            ctx.arc(x, y, grid.r, 0, 2 * Math.PI);
        }
    ctx.fill();
    ctx.save();
    ctx.strokeStyle = '#b3bfd428';
    ctx.lineWidth = .85;
    ctx.beginPath();
    for (let x = grid.x0; x < grid.x1; x += grid.spacing * 3)
        for (let y = grid.y0; y < grid.y1; y += grid.spacing * 3) {
            ctx.moveTo(x - 4, y);
            ctx.lineTo(x + 4, y);
            ctx.moveTo(x, y - 4);
            ctx.lineTo(x, y + 4);
        }
    ctx.stroke();
    ctx.restore();
    return ctx;
}
