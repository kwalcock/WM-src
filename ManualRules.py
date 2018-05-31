import math
import os
import string
from FrameNetRefine import FrameNetRefiner
from StanfordInfo import DataExtractor
from nltk.stem.wordnet import WordNetLemmatizer


targetN= ['sudan', 'famine', 'food', 'hunger', 'drought', 'nutrition']
targetV= ['affect', 'cause', 'focus', 'need', 'suffer', 'occur']
# causalVerbs= ['affect', 'impact', 'bear_upon', 'bear_on', 'touch_on', 'touch', 'involve', 'regard', 'feign', 'sham', 'pretend', 'dissemble', 'impress', 'strike', 'cause', 'do', 'make', 'induce', 'stimulate', 'mean', 'intend', 'entail', 'imply', 'signify', 'stand_for', 'think', 'think_of', 'have_in_mind', 'result', 'ensue', 'leave', 'lead', 'take', 'direct', 'conduct', 'guide', 'head', 'run', 'go', 'pass', 'extend', 'top', 'contribute', 'conduce', 'precede', 'moderate', 'chair']
aux= ['be', 'can', 'could', 'dare', 'do', 'have', 'may', 'might', 'must', 'ought', 'shall', 'should', 'will', 'would']
#Don't include "NEED", it serves BOTH as modal verb AND normal verb: eg "I need food.". What about "get"?

# anaphoricVerbs=['reveal','compare', 'equate','state', 'say', 'tell', 'allege', 'aver', 'suppose', 'read', 'order', 'enjoin', 'pronounce', 'articulate', 'enounce', 'sound_out', 'enunciate', 'talk', 'speak', 'utter', 'mouth', 'verbalize', 'verbalise', 'address', 'report', 'describe', 'account', 'cover', 'show', 'demo', 'exhibit', 'present', 'demonstrate', 'prove', 'establish', 'shew', 'testify', 'bear_witness', 'evidence', 'picture', 'depict', 'render', 'express', 'evince', 'indicate', 'point', 'designate', 'show_up', 'register', 'record', 'usher', 'narrate', 'recount', 'recite', 'assure', 'distinguish', 'separate', 'differentiate', 'secern', 'secernate', 'severalize', 'severalise', 'tell_apart', 'spill', 'spill_the_beans', 'let_the_cat_out_of_the_bag', 'tattle', 'blab', 'peach', 'babble', 'sing', 'babble_out', 'blab_out', 'lecture', 'bespeak', 'betoken', 'signal', 'argue', 'suggest']
# estVerbs = ['estimate', 'expect']
verbTags=["VB", "VBP", "VBD", "VBZ", "VBN", "VBG"] #VBN and VBG maybe?
nounTags= ["NN", "NNS", "NNP", "NNPS", "JJ"]

class CandidateEvents:

    def __init__(self, file, dir):
        self.file= file
        self.dir = dir
        self.stanfordLoader= DataExtractor(file, dir)
        self.refiner= FrameNetRefiner()
        self.lmtzr = WordNetLemmatizer()

    def getVerbEvents(self, sentenceIndex, events, entities, refine=True):
        data= self.stanfordLoader.getDataPerSentence(sentenceIndex)
        #sentence, tokens, mapping, loc, time, depCurr = self.data[sentenceIndex]
        pos= data["pos"]
        lemmas= data["lemmas"]
        tokens= data["tokens"]
        sentence= data["sentence"]
        spans = data['spans']
        sentenceEvents = events
        for index in range(len(lemmas)):
        #for item in lemmas:
            if pos[index] in verbTags and lemmas[index] not in aux:
            #if item["pos"] in verbTags and (item["lemma"] not in aux):
                flag= True
                frame= ""
                if refine:
                    flag, frame= self.refiner.refineWord(sentence, lemmas[index], pos[index])
                if flag:
                    token= tokens[index]
                    ###Somewhere here differentiate to get the list of entities and the list of nominal Events????
                    ##Pass only entities into SRL finder, because otherwise it is gonna be inefficient
                    ##Can we do it in another slot? Configure

                    #srlOut, nomBool= self.recognizeNomEventuality(token, data['NPs'])
                    span= spans[index]
                    if span in events:
                        pass
                    else:
                        srlOut= self.getDependencies(sentenceIndex, index+1, entities)
                        newEvent={"trigger": token["token"], "lemma": lemmas[index], "start": token["start"], "end": token["end"], "index": index,
                                  "frame": frame, "temporal": data["temporal"], "location": data["location"]}
                        newEvent.update(srlOut)
                        sentenceEvents.append(newEvent)
        return sentenceEvents

    def getLocAndTime(self, sentenceIndex):
        sentence, tokens, mapping, loc, time, depCurr= self.data[sentenceIndex]
        return {'location': loc, 'time': time}

    def dataSize(self):
        return self.stanfordLoader.getDataSize()

    def getSentence(self, sentenceIndex):
        sentence, tokens, mapping, loc, time, depCurr = self.data[sentenceIndex]
        return sentence

    def getTokens(self, sentenceIndex):
        sentence, tokens, mapping, loc, time, depCurr = self.data[sentenceIndex]
        return tokens

    def getAllEvents(self):
        allEvents=[]
        for index in range(self.stanfordLoader.getDataSize()):
            events, entities = self.classifyNominals(index)

            events= self.getVerbEvents(index, events, entities)
            #sentenceEvents= verbalEvents+ nomEvents
            allEvents.append(events)
        return allEvents

    # def getEventsWithDependencies(self, sentenceIndex, entities):
    #     events= self.getVerbEvents(sentenceIndex)
    #     #sentence, tokens, mapping, loc, time, depCurr = self.data[sentenceIndex]
    #     eventsWithDeps=[]
    #     if len(events)==0: return []
    #     for event in events:
    #         index= event["index"]
    #         dependencies= self.getDependencies(sentenceIndex, index, entities)
    #         event.update(dependencies)
    #         eventsWithDeps.append(event)
    #     return eventsWithDeps

    def getDependencies(self, sentenceIndex, index, entities):
        deps= self.stanfordLoader.getDependencies(sentenceIndex)
        agent= []
        patient= []
        #otherDeps={}
        allDeps={}
        for dependency in deps:
            governor = int(dependency['governor'])
            depType = dependency['dep']
            dependent = str(dependency['dependentGloss'])
            depIndex = int(dependency['dependent'])
            if governor == index:
                if depType in allDeps.keys():
                    prev= allDeps[depType]
                    allDeps[depType] = prev+ [dependent]
                else:
                    allDeps[depType]= [dependent]
        passive= False
        if "nsubj" in allDeps.keys():
            agent= allDeps["nsubj"]
        if "nsubjpass" in allDeps.keys():
            patient=  allDeps["nsubjpass"]
            passive= True
        elif "dobj" in allDeps.keys():
            patient = allDeps["dobj"]
        if patient== [] or passive:
            for rel in allDeps.keys():
                if "nmod" in rel:
                    if agent == [] and passive:
                        agent= allDeps[rel]
                    elif patient== []:
                        patient= allDeps[rel]
        out={'agent':"", 'patient':""}
        if agent!= []:
            out['agent']= self.mapToEntity(agent, entities)
        if patient!= []:
            out['patient']= self.mapToEntity(patient, entities)
        return out

    def mapToEntity(self, terms, NPs):
        normalized=""
        for span in NPs.keys():
            np= NPs[span]
            entity= np["token"]
            norm= ""
            for term in terms:
                if term in entity:
                    norm= entity
            normalized+= norm+', '
        normalized = normalized.strip(', ')
        return normalized

    def writeEvents(self, sentIndex, currIndex, ws1, entities):
        events= self.getEventsWithDependencies(sentIndex)
        sentence= self.getSentence(sentIndex)
        for event in events:
            ws1["A" + str(currIndex)] = str(self.file)
            ws1["B" + str(currIndex)] = 'E'+str(currIndex-1)
            ws1["C" + str(currIndex)] = event['trigger']
            ws1["D" + str(currIndex)] = event['frame']
            if 'location' in event:
                ws1["E" + str(currIndex)] = event['location']
            if 'time' in event:
                ws1["F" + str(currIndex)] = event['time']
            if 'agent' in event:
                agent=  self.mapToEntity(event['agent'], entities)
                ws1["G" + str(currIndex)] = agent
            if 'patient' in event:
                patient = self.mapToEntity(event['patient'], entities)
                ws1["H" + str(currIndex)] = patient
            ws1["I" + str(currIndex)] = sentence
            currIndex+=1
        return currIndex

    def classifyNominals(self, sentenceIndex):
        events = {}
        entities={}
        data = self.stanfordLoader.getDataPerSentence(sentenceIndex)
        sentence = data["sentence"]
        nominals = data["NPs"]
        for item in nominals:
            words = item["token"].split(' ')
            span= (item['start'], item['end'])
            if len(item['eventuality'])>0:
                entities[span]= {'token': words, 'location': data['location'], 'temporal': data['temporal'], 'qualifier': item['qualifier']}
                #entities.append(item)
                event = item['eventuality']
                lemma= event['lemma']
                boolean, frames = self.refiner.refineWord(sentence, lemma, 'v')
                if boolean:
                    eventSpan= (event['start'], event['end'])
                    events[eventSpan]= {'trigger': event['token'], 'location': data['location'], 'temporal': data['temporal'], 'patient': words, 'frame': frames[0]}
                #events.append(item['eventuality'])
                
            else:
                ###Filter from Ontology...
                lemma = item['headLemma']
                boolean, frames = self.refiner.refineWord(sentence, lemma, 'n')
                if boolean:
                    events[span] = {'trigger': words, 'frame': frames[0], 'location': data['location'], 'temporal': data['temporal']}
                    # events.append(
                    #     {'trigger': words, 'frame': frames[0], 'location': data['location'], 'temporal': data['temporal'],
                    #      'start': item['start'], 'end': item['end']})
                else:
                    #entities.append(item)
                    entities[span] = {'trigger': words, 'location': data['location'], 'temporal': data['temporal'],
                                      'qualifier': item['qualifier']}
                    # entities.append({'trigger': words, 'location': data['location'], 'temporal': data['temporal'],
                    #      'start': item['start'], 'end': item['end']})
        return events, entities

    def nominalEvents(self, sentence, candidateEvents):
        events=[]
        entities=[]
        for phrase in candidateEvents:
            eventFlag=False
            for word in phrase.split(' '):
                lemma= self.lmtzr.lemmatize(word, 'n')
                boolean, frames= self.refiner.refineWord(sentence, lemma, 'n')
                eventFlag+= boolean
            if eventFlag>0:
                events.append(phrase)
            else:
                entities.append(phrase)
        return entities, events
