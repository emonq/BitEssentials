FROM python:3.10-slim
ADD . /BitEssentials
WORKDIR /BitEssentials
RUN pip install -r requirements.txt
ENTRYPOINT ["python"]
CMD ["main.py"]
