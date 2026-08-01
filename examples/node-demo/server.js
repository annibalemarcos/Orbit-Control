const http = require('node:http');

const port = Number(process.env.PORT || 43127);
const server = http.createServer((_request, response) => {
  response.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
  response.end('Orbit Control: Node.js OK\n');
});

server.listen(port, '127.0.0.1', () => {
  console.log(`NODE_READY http://127.0.0.1:${port}`);
});

function shutdown() {
  server.close(() => process.exit(0));
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
