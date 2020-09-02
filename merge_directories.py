import os

phonbank_dir = os.path.abspath("/shared_hd1/phonbank-xml/2020.1/candidate/phonbank.talkbank.org/data-xml")
childes_dir = os.path.abspath("/shared_hd1/childes-xml/2020.1/candidate/childes.talkbank.org/data-xml")
global_dir = os.path.abspath("/shared_hd1/childes-db-xml")
os.system("mkdir " + str(global_dir))


for d in [phonbank_dir, childes_dir]:
    data_cols = os.listdir(d)
    global_cols = os.listdir(global_dir)
  

    for col in data_cols:
        global_coll_path = os.path.join(global_dir, col)
        src_coll_path = os.path.join(d, col)
        if col == "Dutch":#Edge case, not tested
            global_coll_path = os.path.join(global_dir, "DutchAfrikaans")
        if col not in global_cols:
            print("Copying " + src_coll_path + " to " + global_coll_path)
            os.system("cp -R " + src_coll_path + " " + global_coll_path) #if the collection is not in the childes-db directory, we can copy the contents over from the source
            
        else: #if collection does exist
            for corpus in os.listdir(src_coll_path):
                if corpus not in os.listdir(global_coll_path):
                    print("Copying " + os.path.join(src_coll_path, corpus) + " to " + os.path.join(global_coll_path, corpus))
                    os.system("cp -R " + os.path.join(src_coll_path, corpus) + " " + os.path.join(global_coll_path, corpus))
                else:
                    subcorp_path = os.path.join(src_coll_path, corpus)
                    for sc in os.listdir(subcorp_path):
                        print("Copying " + os.path.join(subcorp_path, sc) + " to " + os.path.join(global_coll_path, corpus, sc))
                        os.system("cp -R " + os.path.join(subcorp_path, sc) + " " + os.path.join(global_coll_path, corpus, sc))

                 
