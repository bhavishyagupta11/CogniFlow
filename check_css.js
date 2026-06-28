const http = require('http');

http.get('http://localhost:3000', res => {
  let html = '';
  res.on('data', c => html += c);
  res.on('end', () => {
    const cssLinks = [...html.matchAll(/href="([^"]+\.css[^"]*)"/g)].map(m => m[1]);
    console.log("CSS Links:", cssLinks);
    
    let found = false;
    let pending = cssLinks.length;
    
    if (pending === 0) console.log("No CSS found");

    cssLinks.forEach(link => {
      const url = link.startsWith('http') ? link : 'http://localhost:3000' + (link.startsWith('/') ? '' : '/') + link;
      http.get(url, cssRes => {
        let css = '';
        cssRes.on('data', c => css += c);
        cssRes.on('end', () => {
          if (css.includes('.katex')) {
            console.log("KATEX CSS FOUND IN:", link);
            found = true;
          }
          pending--;
          if (pending === 0 && !found) console.log("KATEX CSS MISSING FROM ALL BUNDLES");
        });
      });
    });
  });
});
