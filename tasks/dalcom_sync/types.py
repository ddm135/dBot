import struct
from pathlib import Path

from .commons import SEQ_LANES, SEQ_PADDING


class Seq:
    def __init__(self, path: str | Path) -> None:
        self.SEQData_Info = {}
        self.SEQData_Tempo = []
        self.SEQData_Object = []
        self.SEQData_Channel = []
        self.SEQData_Event = []
        self.count = 0
        self.invalid_count = 0

        with open(path, "rb") as seq:
            self.SEQData_Info["layout"] = struct.unpack("<I", seq.read(4))[0]
            if self.SEQData_Info["layout"] not in SEQ_PADDING:
                return
            self.SEQData_Info["tickLength"] = struct.unpack("<I", seq.read(4))[0]
            self.SEQData_Info["secLength"] = struct.unpack("<d", seq.read(8))[0]
            self.SEQData_Info["tickPerBeat"] = struct.unpack("<I", seq.read(4))[0]
            seq.seek(SEQ_PADDING[self.SEQData_Info["layout"]], 1)
            self.SEQData_Info["beatPerTick"] = struct.unpack("<d", seq.read(8))[0]
            self.SEQData_Info["tempoCount"] = struct.unpack("<I", seq.read(4))[0]
            self.SEQData_Info["objectCount"] = struct.unpack("<I", seq.read(4))[0]
            self.SEQData_Info["channelCount"] = struct.unpack("<I", seq.read(4))[0]
            self.SEQData_Info["eventCount"] = struct.unpack("<I", seq.read(4))[0]
            self.SEQData_Info["measureCount"] = struct.unpack("<I", seq.read(4))[0]
            self.SEQData_Info["beatCount"] = struct.unpack("<I", seq.read(4))[0]
            self.SEQData_Info["type"] = struct.unpack("<I", seq.read(4))[0]
            seq.seek(SEQ_PADDING[self.SEQData_Info["layout"]], 1)

            for i in range(self.SEQData_Info["tempoCount"]):
                tempo = {}
                tempo["tick"] = struct.unpack("<I", seq.read(4))[0]
                tempo["tickEnd"] = struct.unpack("<I", seq.read(4))[0]
                tempo["sec"] = struct.unpack("<f", seq.read(4))[0]
                tempo["secEnd"] = struct.unpack("<f", seq.read(4))[0]
                tempo["beatPerMinute"] = struct.unpack("<d", seq.read(8))[0]
                tempo["beatPerMeasure"] = struct.unpack("<I", seq.read(4))[0]
                seq.seek(SEQ_PADDING[self.SEQData_Info["layout"]], 1)
                tempo["measurePerBeat"] = struct.unpack("<d", seq.read(8))[0]
                tempo["measurePerTick"] = struct.unpack("<d", seq.read(8))[0]
                tempo["tickPerMeasure"] = struct.unpack("<I", seq.read(4))[0]
                seq.seek(SEQ_PADDING[self.SEQData_Info["layout"]], 1)
                tempo["beatPerSec"] = struct.unpack("<d", seq.read(8))[0]
                tempo["secPerBeat"] = struct.unpack("<d", seq.read(8))[0]
                tempo["tickPerSec"] = struct.unpack("<d", seq.read(8))[0]
                tempo["secPerTick"] = struct.unpack("<d", seq.read(8))[0]
                tempo["measurePerSec"] = struct.unpack("<d", seq.read(8))[0]
                tempo["secPerMeasure"] = struct.unpack("<d", seq.read(8))[0]
                tempo["measureStart"] = struct.unpack("<I", seq.read(4))[0]
                tempo["measureCount"] = struct.unpack("<I", seq.read(4))[0]
                self.SEQData_Tempo.append(tempo)

            last = {"dataLen": struct.unpack("<I", seq.read(4))[0]}
            if last["dataLen"]:
                last["data"] = seq.read(last["dataLen"]).decode("utf-8")
            for i in range(self.SEQData_Info["objectCount"] - 1):
                obj = {
                    "property": struct.unpack("<I", seq.read(4))[0],
                    "dataLen": struct.unpack("<I", seq.read(4))[0],
                }
                if obj["dataLen"]:
                    obj["data"] = seq.read(obj["dataLen"]).decode("utf-8")
                    self.SEQData_Object.append(obj)
            last["property"] = struct.unpack("<I", seq.read(4))[0]
            if last["dataLen"]:
                self.SEQData_Object.append(last)

            for i in range(self.SEQData_Info["channelCount"]):
                channel = {
                    "eventCount": struct.unpack("<I", seq.read(4))[0],
                    "property": struct.unpack("<I", seq.read(4))[0],
                }
                self.SEQData_Channel.append(channel)

            for i in range(self.SEQData_Info["eventCount"]):
                event = {
                    "tick": struct.unpack("<I", seq.read(4))[0],
                    "duration": struct.unpack("<I", seq.read(4))[0],
                    "channelId": struct.unpack("<I", seq.read(4))[0],
                    "objectId": struct.unpack("<I", seq.read(4))[0],
                    "property": struct.unpack("<I", seq.read(4))[0],
                }

                if i and i != self.SEQData_Info["eventCount"] - 1:
                    if (
                        event["tick"] in range(self.SEQData_Info["tickLength"])
                        and not event["duration"]
                        and event["channelId"] in SEQ_LANES[self.SEQData_Info["type"]]
                    ):
                        self.count += 1
                    else:
                        self.invalid_count += 1
                seq.seek(SEQ_PADDING[self.SEQData_Info["layout"]], 1)
                self.SEQData_Event.append(event)
