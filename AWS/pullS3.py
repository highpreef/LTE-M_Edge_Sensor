"""
Author: David Jorge

This library acts as an API between the dashboard app and AWS. It allows for data to be pulled
from AWS, and parsed/saved accordingly into more convenient formats.
"""

import binascii
import barcode
import pandas
from barcode.writer import ImageWriter
import boto3
from PIL import Image, ImageFile
from io import BytesIO
import datetime


def datetimeToString(dt):
    """
    Converts datetime object into string for file naming.

    :param dt: datetime object.
    :return: string.
    """
    return str(dt)[:10] + "-" + str(dt)[11:13] + "-" + str(dt)[14:16] + "-" + str(dt)[17:19]


def saveBarcode(type, payload, filename):
    """
    Create barcode image.

    :param type: Barcode type.
    :param payload: Barcode payload.
    :param filename: File name.
    """
    with open("./assets/{}-b.png".format(filename), 'wb') as f:
        if type == "EAN8":
            barcode.EAN8(payload, writer=ImageWriter()).write(f)
        elif type == "UPCA":
            barcode.UPCA(payload, writer=ImageWriter()).write(f)
        elif type == "ISBN10":
            barcode.ISBN10(payload, writer=ImageWriter()).write(f)
        elif type == "EAN13":
            barcode.EAN13(payload, writer=ImageWriter()).write(f)
        elif type == "ISBN13":
            barcode.ISBN13(payload, writer=ImageWriter()).write(f)
        elif type == "CODE39":
            barcode.Code39(payload, writer=ImageWriter()).write(f)
        else:
            barcode.Code128(payload, writer=ImageWriter()).write(f)


def roundTime(dt=None, roundTo=60):
    """Round a datetime object to any time lapse in seconds
    dt : datetime.datetime object, default now.
    roundTo : Closest number of seconds to round to, default 1 minute.
    Author: Thierry Husson 2012 - Use it as you want but don't blame me.
    """
    if dt == None: dt = datetime.datetime.now()
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds + roundTo / 2) // roundTo * roundTo
    return dt + datetime.timedelta(0, rounding - seconds, -dt.microsecond)


def getIndexes(dfObj, value):
    """ Get index positions of value in dataframe i.e. dfObj."""
    listOfPos = list()
    # Get bool dataframe with True at positions where the given value exists
    result = dfObj.isin([value])
    # Get list of columns that contains the value
    seriesObj = result.any()
    columnNames = list(seriesObj[seriesObj == True].index)
    # Iterate over list of columns and fetch the rows indexes where value exists
    for col in columnNames:
        rows = list(result[col][result[col] == True].index)
        for row in rows:
            listOfPos.append((row, col))
    # Return a list of tuples indicating the positions of value in the dataframe
    return listOfPos


class pullS3:
    """
    Class for managing and processing data pulls from aws
    """

    def __init__(self):
        """
        files: List of filenames processed during instance lifetime
        mostRecent: String - Most recently added filename from aws.
        count: Dictionary - stores count of condition variable from images.
        df: Pandas dataframe - stores date and count information in hourly intervals.
        """
        self.s3 = boto3.resource(
            service_name='s3',
            region_name='eu-west-2',
            aws_access_key_id='#',
            aws_secret_access_key='#'
        )
        self.files = []
        self.mostRecent = None
        self.count = {"Parcel": 0, "Damaged Parcel": 0}
        self.df = pandas.DataFrame(columns=["Date", "Count"])

    def flushBucket(self, bucketname='intern-cam'):
        """
        Flushes target bucket in AWS. Use with caution.

        :param bucketname: S3 bucket name
        """
        self.s3.Bucket(bucketname).objects.all().delete()

    def pull(self):
        """
        Pulls data from S3 bucket in AWS and processes it.

        :return: Most Recent file name, Parcel Condition Label
        """
        # Print available bucket names
        for bucket in self.s3.buckets.all():
            # print(bucket.name)
            pass
        # Get bucket size
        size = 0
        for obj in self.s3.Bucket('intern-cam').objects.all():
            size += 1
            # print(obj.get()['Body'].read())

        images = []  # List of images as byte arrays
        parsing = False  # Flags whether or not an image the current AWS bucket entry is part of an image
        metadata = None  # Entry metadata

        """
        Each detection by the camera is sent to AWS in the following format:
        {Image Start,__headers__}   # marks the start of an entry, __headers__ is comma separated
        image hex string            # There can be multiple image hex strings
        {Image End}                 # marks the end of an entry
        """
        for obj in self.s3.Bucket('intern-cam').objects.all():
            if "Image Start" in obj.get()['Body'].read().decode():
                parsing = True
                arr = bytearray()
                metadata = obj.get()['Body'].read().decode().replace('}', "").split(',')[1:]
                if len(metadata) < 1:
                    parsing = False
                continue
            if parsing and obj.get()['Body'].read().decode() != "{Image Start}":
                if obj.get()['Body'].read().decode() == "{Image End}":
                    images.append((arr, obj.get()['LastModified'], metadata))
                    metadata = None
                    parsing = False
                    continue
                arr.extend(binascii.unhexlify(obj.get()['Body'].read()))
        # print(images)

        # Get most recent entry
        newest = None
        if images:
            newest = images[0]

        # Save parsed images as files. Same entries are not processed more than once per instance
        # count dict and df instance variables are updated accordingly
        for img in images:
            if not datetimeToString(img[1]) in self.files:
                im = Image.open(BytesIO(img[0]))
                # im.show()
                im.save("./assets/{}.png".format(datetimeToString(img[1])))
                if img[2]:
                    saveBarcode(img[2][0], img[2][1], datetimeToString(img[1]))
                    self.count[img[2][2]] += 1
                self.files.append(datetimeToString(img[1]))
                roundDate = roundTime(img[1], 60 * 60)
                if roundDate not in self.df.values:
                    self.df = self.df.append({"Date": roundDate, "Count": 0}, ignore_index=True)
                loc = getIndexes(self.df, roundDate)[0][0]
                self.df.at[loc, "Count"] += 1

            newest = img
        print("Pulled Data from AWS!")
        self.mostRecent = (datetimeToString(newest[1]), newest[2][2])


if __name__ == "__main__":
    obj = pullS3()
    obj.pull()
    # print(obj.count)
    # print(obj.df)
    # obj.pull()
    # print(obj.count)
    # print(obj.df)
