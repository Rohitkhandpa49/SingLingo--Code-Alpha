# Deployment guide status

The repository currently supports local frontend and backend development with a local MongoDB container. Production deployment is not configured. Before deployment, define and validate frontend/backend containers, secure environment configuration, HTTPS/WSS termination, MongoDB Atlas access controls, health checks, structured logging, shared rate-limit storage, and operational monitoring.

The browser downloads the MediaPipe WebAssembly runtime and hand-landmarker model from their configured public asset hosts. Camera frames remain local; only normalized hand landmarks are sent to the backend. Production deployments must configure `NEXT_PUBLIC_WS_BASE_URL` to a trusted `wss://` endpoint, set `FRONTEND_ORIGIN` to the exact application origin, and use secure session cookies. Add shared WebSocket connection/rate controls at the gateway, and do not configure a gesture checkpoint until its dataset provenance, supported labels, and evaluation are documented.
