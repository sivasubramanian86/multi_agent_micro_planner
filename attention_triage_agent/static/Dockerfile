FROM nginx:alpine

# Copy custom Nginx config to proxy API requests and solve CORS
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the static HTML, CSS, and JS files to Nginx's web directory
COPY index.html /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/

# Expose port 80 (required by Cloud Run)
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
