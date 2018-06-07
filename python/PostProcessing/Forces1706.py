import os.path as path
import numpy as np
from glob import glob as glob
from PostProcessingIO import isNumber, fftAnalysis, filterData, toCoefficient
from collections import defaultdict


class Forces:

    _TIME = 0
    _TOTAL_X = 1
    _TOTAL_Y = 2
    _TOTAL_Z = 3
    _PRESSURE_X = 4
    _PRESSURE_Y = 5
    _PRESSURE_Z = 6
    _VISCOUS_X = 7
    _VISCOUS_Y = 8
    _VISCOUS_Z = 9

    def __init__(self,
                 inputpath,
                 scaleTime = 1,
                 scaleForces = 1,
                 average = False,
                 FFT = False,
                 verbose = True):

        self._inputpath = inputpath
        self._verbose = verbose

        # parse the input path and check if file or directory
        if path.exists(inputpath):
            # if inputpath is a file, try to open the file and read it
            if path.isfile(inputpath):
                self._rawForces = self._readForceFile(inputpath)
            elif path.isdir(inputpath):
                self._timeDirs = []
                self._rawForces = []
                # iterate over the time directories, read in the forces and append them
                for timeDir in glob(path.join(inputpath, "*")):
                    if isNumber(timeDir.split("/")[-1]):
                        self._verbosePrint("processing time dir {}".format(timeDir))
                        self._timeDirs.append(timeDir)
                        # get the force files
                        for forcefile in glob(path.join(timeDir, "force*.dat")):
                            self._verbosePrint("processing: {}".format(forcefile))
                            self._rawForces.append(self._readForceFile(forcefile))

                # generate a numpy matrix containing all forces
                self._rawForces = np.concatenate(self._rawForces)
                # sort the matrix by sorting after the first column (time)
                self._rawForces = self._rawForces[self._rawForces[:,0].argsort()]

            # all forces should be loaded by now
            # build a "nice" dict with the forces                    
            pos = iter(range(1,10))
            self.forces = dict()
            self.forces["time"] = self._rawForces[:,self._TIME]/scaleTime
            for forceType in ("total", "pressure", "viscous"):
                self.forces[forceType] = {}
                for component in "x", "y", "z":
                    self.forces[forceType][component] = self._rawForces[:,next(pos)]/scaleForces
            if average:
                self.calculateAveragesStd()
            if FFT:
                raise Warning("not implemented yet!")
        else:
            raise IOError("could not find file: {}".format(inputpath))

    def _readForceFile(self, filepath):
        raw = []

        with open(filepath, 'r') as filehandle:
            for line in filehandle:
                tmp = [x.strip('(').strip(')') for x in line.split()]
                if len(tmp) == 0:
                    continue
                elif tmp[0] == '#':
                    continue
                elif len(tmp) != 10:
                    continue
                else:
                    try:
                        raw.append([ float(i) for i in tmp ])
                    except ValueError:
                        print("could not convert string to float in line:")
                        print("\t" + line)
                        print("in file:")
                        print("\t" + filepath)

        filehandle.close()
        raw = np.array(raw)
        return raw

    def _getTimeIndex(self, time):
        index = 0
        while self._rawForces[index,0] < time and index < len(self._rawForces[:,0]):
            index += 1
        return index

    def _getIndices(self, startTime = 0, endTime = 0):
        startIndex = 0
        endIndex = len(self.forces["time"])
        if startTime == 0 and endTime == 0:
            self._verbosePrint("start index {} end index {}".format(startIndex, endIndex))
        elif startTime > 0 and endTime == 0:
            startIndex = self._getTimeIndex(startTime)
            self._verbosePrint("start index {} end index {}".format(startIndex, endIndex))
        elif startTime == 0 and endTime > 0:
            endIndex = self._getTimeIndex(endTime)
            self._verbosePrint("start index {} end index {}".format(startIndex, endIndex))
        elif startTime > 0 and endTime > 0:
            startIndex = self._getTimeIndex(startTime)
            endIndex = self._getTimeIndex(endTime)
            self._verbosePrint("start index {} end index {}".format(startIndex, endIndex))
        else:
            print("undefined behaviour!")
            startIndex=0
            endIndex=0
        return (startIndex, endIndex)

    def calculateAveragesStd(self, startTime = 0, endTime = 0):

        self.averageForces = {}
        self.stdForces = {}

        startIndex, endIndex = self._getIndices(startTime, endTime)

        for forceType in ("total", "pressure", "viscous"):
            self.averageForces[forceType] = {}
            self.stdForces[forceType] = {}
            for component in ("x", "y", "z"):
                self.averageForces[forceType][component] = np.average(self.forces[forceType][component][startIndex:endIndex])
                self.stdForces[forceType][component] = np.std(self.forces[forceType][component][startIndex:endIndex])

        return (self.averageForces, self.stdForces)


    def _verbosePrint(self, message):
        if self._verbose == True:
            print(message)

    def getMaxTime(self):
        self._verbosePrint("max time is {}".format(self.forces["time"][-1]))
        return self.forces["time"][-1]


    def filterForces(self, startTime = 0, endTime = 0, filterFunction = "flat", filterWindow = 11):
        if filterWindow % 2 == 0:
            raise Exception("filterWindow needs to be an uneven number!")

        startIndex, endIndex = self._getIndices(startTime, endTime)
        endTimeIndex = int(len(self._rawForces[:,self._TIME]) - ((filterWindow - 1)/2))

        self.filteredForces = {}
        self.filteredForces["time"] =  self._rawForces[int((filterWindow - 1)/2):endTimeIndex,self._TIME]

        for forceType in ("total", "pressure", "viscous"):
            self.filteredForces[forceType] = {}
            for component in ("x", "y", "z"):
                self.filteredForces[forceType][component] = filterData(self.forces[forceType][component][startIndex:endIndex], filterWindow, filterFunction)

        return self.filteredForces

    def calculateFilteredAveragesStd(self, startTime = 0, endTime = 0):

        if hasattr(self, "filteredForces") == False:
            raise Exception("missing attribute filteredForces. Please run filterForces prior to calculateFilteredAveragesStd!")

        self.averageFilteredForces = {}
        self.stdFilteredForces = {}
        startIndex, endIndex = self._getIndices(startTime, endTime)
        for forceType in ("total", "pressure", "viscous", "porous"):
            self.averageFilteredForces[forceType] = {}
            self.stdFilteredForces[forceType] = {}
            for component in ("x", "y", "z"):
                self.averageFilteredForces[forceType][component] = np.average(self.filteredForces[forceType][component][startIndex:endIndex])
                self.stdFilteredForces[forceType][component] = np.std(self.filteredForces[forceType][component][startIndex:endIndex])

        return (self.averageFilteredForces, self.stdFilteredForces)

    def getMinTime(self):
        self._verbosePrint("min time is {}".format(self.forces["time"][0]))
        return self.forces["time"][0]

    ## define a method for getting forces by time
    def getForceByTime(self,  startTime = 0, endTime = 0, forceType = "total", forceComponent = "x"):
        startIndex, endIndex = getIndices(startTime, endTime)
        return self.forces[forceType][forceComponent][startIndex:endIndex]

    def _verbosePrint(self, message):
        if self._verbose == True:
            print(message)

class ForceCoefficients(Forces):
    def __init__(self, inputpath, rho = 1, velocity = 1, area = 2, average = True, FFT = False, verbose = True):

        self._inputpath = inputpath
        self._verbose = verbose

        self._forceObject = Forces(inputpath)

