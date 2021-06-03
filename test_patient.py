import tp_structs

a1 = tp_structs.TestSet("TEST_SAMPLE_1", "1", "TEST_UE2", Results=[tp_structs.Result("Sodium", 130, "mmol/L", "01.01.2000 08:59"), 
                                                                   tp_structs.Result("Potassium", 4.0, "mmol/L", "01.01.2000 08:59"),
                                                                   tp_structs.Result("Magnesium", 0.7, "mmol/L", "01.01.2000 08:59")], 
                        Comments=["Wow!", "Cool tp_structs.TestSet", "Call Biochemist NOW!!"], AuthedOn="01.01.2000 09:00", OverrideID=True)
#a2 = tp_structs.TestSet("TEST_SAMPLE_1", "4", "TEST_UE2", Results=[], Comments=["Bang bang bang!"])
#a3 = tp_structs.TestSet("TEST_SAMPLE_1", "5", "TEST_UE2", Results=[], Comments=["Pull", "My Devil Trigger"])
a=tp_structs.Specimen("TEST_SAMPLE_1", OverrideID=True)
a.Sets = [a1]#, a2, a3]

b1 = tp_structs.TestSet("TEST_SAMPLE_2", "1", "TEST_UE2", Results=[tp_structs.Result("Sodium", 123, "mmol/L", "01.01.2000 09:59"),
                                                                   tp_structs.Result("Potassium", 3.5, "mmol/L", "01.01.2000 09:59"),
                                                                   tp_structs.Result("Magnesium", 0.8, "mmol/L", "01.01.2000 09:59")], 
                        Comments=["Wow!", "Cool tp_structs.TestSet", "Call Biochemist NOW!!"], AuthedOn="01.01.2000 10:00", OverrideID=True)
#b2 = tp_structs.TestSet("TEST_SAMPLE_2", "2", "TEST_UE2", Results=[], Comments=["Frustration"])
#b3 = tp_structs.TestSet("TEST_SAMPLE_2", "3", "TEST_UE2", Results=[], Comments=["Is getting bigger"])
b=tp_structs.Specimen("TEST_SAMPLE_2", OverrideID=True)
b.Sets = [b1]#, b2, b3]


c1 = tp_structs.TestSet("TEST_SAMPLE_3", "1", "TEST_UE2", Results=[tp_structs.Result("Sodium", 129, "mmol/L", "01.01.2000 10:58"),
                                                                   tp_structs.Result("Potassium", 4.5, "mmol/L", "01.01.2000 10:58"),
                                                                   tp_structs.Result("Magnesium", 0.6, "mmol/L", "01.01.2000 10:58")], 
                        Comments=["Wow!", "Cool tp_structs.TestSet", "Call Biochemist NOW!!"], AuthedOn="01.01.2000 11:00", OverrideID=True)
#c2 = tp_structs.TestSet("TEST_SAMPLE_3", "2", "TEST_UE2", Results=[], Comments=["Frustration"])
#c3 = tp_structs.TestSet("TEST_SAMPLE_3", "3", "TEST_UE2", Results=[], Comments=["Is getting bigger"])
c=tp_structs.Specimen("TEST_SAMPLE_3", OverrideID=True)
c.Sets = [c1]#, c2, c3]


d1 = tp_structs.TestSet("TEST_SAMPLE_4", "1", "TEST_UE2", Results=[tp_structs.Result("Sodium", 135, "mmol/L", "02.01.2000 09:00"),
                                                                   tp_structs.Result("Potassium", 5.0, "mmol/L", "02.01.2000 09:00"),
                                                                   tp_structs.Result("Magnesium", 0.5, "mmol/L", "02.01.2000 09:00")], 
                        Comments=["Wow!", "Cool tp_structs.TestSet", "Call Biochemist NOW!!"], AuthedOn="02.01.2000 09:00", OverrideID=True)
#d2 = tp_structs.TestSet("TEST_SAMPLE_4", "2", "TEST_UE2", Results=[], Comments=["Frustration"])
#d3 = tp_structs.TestSet("TEST_SAMPLE_4", "3", "TEST_UE2", Results=[], Comments=["Is getting bigger"])
d=tp_structs.Specimen("TEST_SAMPLE_4", OverrideID=True)
d.Sets = [d1]#, d2, d3]


e1 = tp_structs.TestSet("TEST_SAMPLE_5", "4", "TEST_UE2", Results=[tp_structs.Result("Sodium", 140, "mmol/L", "03.01.2000 09:00"),
                                                                   tp_structs.Result("Potassium", 4.7, "mmol/L", "03.01.2000 09:00"),
                                                                   tp_structs.Result("Magnesium", 0.4, "mmol/L", "03.01.2000 09:00")], 
                        Comments=["Bang bang bang!"], AuthedOn="03.01.2000 09:00", OverrideID=True)
#e2 = tp_structs.TestSet("TEST_SAMPLE_5", "5", "TEST_UE2", Results=[], Comments=["Pull", "My Devil Trigger"])
#e3 = tp_structs.TestSet("TEST_SAMPLE_5", "6", "TEST_UE2", Results=[], Comments=["Embrace", "The Darkness", "That's Within Me"])
e=tp_structs.Specimen("TEST_SAMPLE_5", OverrideID=True)
e.Sets = [e1]#, e2, e3]


f1 = tp_structs.TestSet("TEST_SAMPLE_6", "4", "TEST_UE2", Results=[tp_structs.Result("Sodium", 138, "mmol/L", "04.01.2000 09:00"),
                                                                   tp_structs.Result("Potassium", 4.5, "mmol/L", "04.01.2000 09:00"),
                                                                   tp_structs.Result("Magnesium", 0.3, "mmol/L", "04.01.2000 09:00")], 
                        Comments=["Bang bang bang!"], AuthedOn="04.01.2000 09:00", OverrideID=True)
#f2 = tp_structs.TestSet("TEST_SAMPLE_6", "5", "TEST_UE2", Results=[], Comments=["Pull", "My Devil Trigger"])
#f3 = tp_structs.TestSet("TEST_SAMPLE_6", "6", "TEST_UE2", Results=[], Comments=["Embrace", "The Darkness", "That's Within Me"])
f=tp_structs.Specimen("TEST_SAMPLE_6", OverrideID=True)
f.Sets = [f1]#, f2, f3]

testPatient = tp_structs.Patient()
testPatient.LName = "Joestar"
testPatient.FName = "Johannes"
testPatient.ID = "00000000"
testPatient.Samples.append(a)
testPatient.Samples.append(f)
testPatient.Samples.append(c)
testPatient.Samples.append(e)
testPatient.Samples.append(b)
testPatient.Samples.append(d)

testPatient.Samples.sort()
