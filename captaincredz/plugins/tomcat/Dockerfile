FROM tomcat:9.0-jre11

RUN cp -r /usr/local/tomcat/webapps.dist/* /usr/local/tomcat/webapps/

COPY tomcat-users.xml /usr/local/tomcat/conf/

RUN sed -i '/RemoteAddrValve/,+1d' /usr/local/tomcat/webapps/manager/META-INF/context.xml

EXPOSE 8080
CMD ["catalina.sh", "run"]