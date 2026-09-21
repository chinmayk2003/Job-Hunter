FROM nginx:1.25-alpine

# Remove default nginx config file
RUN rm /etc/nginx/nginx.conf

# Copy custom config file
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
