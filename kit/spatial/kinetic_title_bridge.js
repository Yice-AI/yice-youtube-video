all('.display-word').forEach((word, i) => {
  tl.fromTo(word, { y: 42, opacity: 0 }, { y: 0, opacity: 1, duration: .14, ease: 'expo.out' }, data.words[i].at);
});
tl.fromTo(q('.bridge-title path'), { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: .2, ease: 'power2.out' }, data.underline_at);
