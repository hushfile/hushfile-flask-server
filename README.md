# hushfile-flask-server
Flask server compatible with the hushfile 1.0 api

## Installation
To run (locally or on a server) nginx is needed for rewriting, the following config can be used:

```
server {
    listen 8000 default_server;
    server_name _;
    root /path/to/hushfile-web/checkout;
    client_max_body_size            1000M;
    location / {
        index                   hushfile.html;
        try_files               $uri /hushfile.html =404;
    }
    location /api/ {
        # hushfile-flask-server port
        proxy_pass http://127.0.0.1:8080;
    }
}
```

