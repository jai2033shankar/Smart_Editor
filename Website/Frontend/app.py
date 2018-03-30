from flask import Flask, render_template, request, jsonify
from PythonMagick import Image
import PythonMagick
from pymongo import MongoClient
from datetime import datetime
from werkzeug.utils import secure_filename
import pytesseract as tesseract
import os
import cv2
import ast
import string
import re
from Helping_Libraries import db
from Helping_Libraries import myocr

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pdftoimage', methods=['POST'])
def pdftoimage():
    time = str(datetime.now())
    time = time.replace(' ', '')
    time = time.replace(':', '')
    pdffile = request.files['pdf']
    pdffile.save(os.path.join('./static/temporary', secure_filename(pdffile.filename)))

    img = Image()
    img.density('300')
    img.read('./static/temporary/' + secure_filename(pdffile.filename))

    size = "%sx%s" % (img.columns(), img.rows())

    output_img = Image(size, "#ffffff")
    output_img.type = img.type
    output_img.composite(img, 0, 0, PythonMagick.CompositeOperator.SrcOverCompositeOp)
    output_img.magick('JPG')
    output_img.quality(90)

    output_jpg = "./static/non_filled_images/" + "nonfilled_" + time + ".jpg"
    output_img.write(output_jpg)
    return render_template('coordinates.html', name = output_jpg)

@app.route('/tesseract', methods=['POST'])
def getTags():
    initialimagename = request.form.get('imagename')
    imagename = initialimagename[:-1]
    initialcoordinates = request.form.get('coordinates')
    coordinates = initialcoordinates[:-1]
    print(coordinates)
    labeldict = {}
    index = 0
    #print(imagename)
    image = myocr.preprocess(imagename)
    # convert str to list
    tcoords = ast.literal_eval(coordinates)
    labellist = []
    label_coordinates = []
    i = 0
    datalist = []
    for x, y, w, h in tcoords:
        x, y, w, h = int(x), int(y), int(w), int(h)
        croppedSection = myocr.cropImage(x, y, w, h, image)
        label = tesseract.image_to_string(croppedSection).replace('\\','')
        print(label)
        coorlist = []
        coorlist.extend([str(index), label, str(x), str(y), str(w), str(h)])

        datalist.append(coorlist)
        index = index + 1
    #print(datalist)
    return render_template('render.html', imagename = imagename, datalist = datalist)

@app.route('/something', methods=['POST'])
def save_labels():
    temp_dict = {'imagename': request.form.get('imagename')}
    counter = int(request.form.get('counter'))
    for i in range(counter):
        # print(request.form.get(str(i)))
        # print(request.form.get(str(i) + "coordinates"))
        # args_dict = {request.form.get(str(i)): request.form.get(str(i) + 'coordinates')}
        temp_key = request.form.get(str(i)).replace('.', '')
        temp_key = myocr.remove_punctuations(temp_key)
        temp_dict[temp_key] = request.form.get(str(i) + 'coordinates').replace('/', '')
    db.insert_data('non_filled', temp_dict)
    cols = db.read_data('non_filled')
    return render_template('index.html', notification = True)

@app.route('/filled')
def filled():
    cols = db.read_data('non_filled')
    images = []
    print(cols)
    for c in cols:
        images.append(c['imagename'])
    #print(images)
    return render_template('filled.html', images=images)

@app.route('/database')
def database():
    cols = db.read_data('non_filled')
    images = []
    for c in cols:
        images.append(c['imagename'])
    #print(images)
    return render_template('database.html', imagepath=images)

@app.route('/script')
def script():
    filled = request.form.get("file")
    print(filled)
    selected = request.form.get("imgname")
    print(selected)
    return render_template('database.html')

@app.route('/ocr', methods = ['POST'])
def ocr():
    labelncoor = {}
    time = str(datetime.now())
    time = time.replace(' ', '')
    time = time.replace(':', '')
    nonfilledimagename = request.form.get('imagename')
    #print(nonfilledimagename)
    pdffile = request.files['pdf']
    pdffile.save(os.path.join('./static/temporary', secure_filename(pdffile.filename)))
    i = 0
    img = Image()
    img.density('300')
    img.read('./static/temporary/' + secure_filename(pdffile.filename))

    size = "%sx%s" % (img.columns(), img.rows())

    output_img = Image(size, "#ffffff")
    output_img.type = img.type
    output_img.composite(img, 0, 0, PythonMagick.CompositeOperator.SrcOverCompositeOp)
    output_img.magick('JPG')
    output_img.quality(90)
    os.mkdir('./static/filled_images/' + time)
    filledimage = "./static/filled_images/" + time + "/" + "filled_" + str(i) + ".jpg"
    output_img.write(filledimage)
    cols = db.read_data('non_filled')
    for c in cols:
        if c['imagename'] == nonfilledimagename:
            del c['_id']
            del c['imagename']
            for key, values in c.items():
                labelncoor[key] = values
    print(labelncoor)
    nonfilledimage = cv2.imread(nonfilledimagename, 0)
    nonfilledimage = cv2.threshold(nonfilledimage, 100, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    nonfilledimagedilated = cv2.dilate(nonfilledimage.copy(), np.ones((2, 2), np.uint8), iterations = 4)
    filledimage = cv2.threshold(cv2.imread(filledimage, 0), 100, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    filledimagedilated = cv2.dilate(filledimage, np.ones((2, 2), np.uint8), iterations=4)

    formvalues = myocr.getNonfilledCroppedSections(nonfilledimage, filledimage, nonfilledimagedilated, filledimagedilated, labelncoor)
    #print(formvalues)
    ## inserting into database
    #insert_data('filled', args_dict=formvalues)
    return render_template('forms.html', formvalues=formvalues)

@app.route('/saveformvalues', methods=['POST'])
def saveformvalues():
    counter = request.form.get('counter')
    formvalues = {}
    for counts in range(int(counter)):
        key = request.form.get(str(counts))
        value = request.form.get(str(counts) + "values")
        formvalues[key] = value
    print(formvalues)
    db.insert_data('filled', args_dict=formvalues)
    return render_template('success.html')

if __name__ == '__main__':
    app.run(debug=True)
