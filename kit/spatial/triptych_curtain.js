all('.curtain-panel').forEach((panel, i) => {
  tl.fromTo(panel.firstElementChild, { scale: 1.13, rotationY: i % 2 ? 3 : -3, xPercent: i % 2 ? 3 : -3 },
    { scale: 1.02, rotationY: 0, xPercent: 0, duration: dur, ease: 'none' }, 0);
});
all('.display-word').forEach((word, i) => {
  tl.fromTo(word, { y: 26, opacity: 0, scale: 1.07 },
    { y: 0, opacity: 1, scale: 1, duration: .14, ease: 'expo.out' }, data.words[i].at);
});
