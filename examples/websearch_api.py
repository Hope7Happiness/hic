from ddgs import DDGS

def search_duckduckgo(query):
    results = DDGS().text(query, max_results=5)
    # print("Result length:", len(results))
        
    # for r in results:
    #     print(f"Title: {r['title']}")
    #     print(f"URL: {r['href']}")
    #     print(f"Snippet: {r['body']}")
    #     print("-" * 20)
    print(results)

search_duckduckgo("Kaiming He")

# Expected Output:

# [{'title': 'Kaiming He', 'href': 'https://en.wikipedia.org/wiki/Kaiming_He', 'body': 'Kaiming He (Chinese: 何恺明; pinyin: Hé Kǎimíng) is a Chinese computer scientist who primarily researches computer vision and deep learning. He is an associate professor at Massachusetts Institute of Technology and works part-time as a Distinguished Scientist at Google DeepMind. He is known as one of the creators of the residual neural network (ResNet) architecture.'}, {'title': 'Kaiming He', 'href': 'https://grokipedia.com/page/kaiming-he', 'body': 'Kaiming He is a Chinese computer scientist and associate professor at the Massachusetts Institute of Technology (MIT), specializing in computer vision and deep learning. He is known for his pioneering work, including the development of ResNet architectures.'}, {'title': 'Kaiming He - Google Scholar', 'href': 'https://scholar.google.com/citations?user=DhtAFkwAAAAJ&hl=en', 'body': 'Kaiming He Associate Professor, EECS, MIT Verified email at mit.edu - Homepage Computer Vision Machine Learning'}, {'title': 'Kaiming He - Associate Professor at MIT | LinkedIn', 'href': 'https://www.linkedin.com/in/kaiming-he-90664838', 'body': "Associate Professor at MIT · Experience: Massachusetts Institute of Technology · Education: Tsinghua University · Location: Cambridge · 34 connections on LinkedIn. View Kaiming He's profile ..."}, {'title': 'IE PhD Alumnus Kaiming He ranked the fifth most highly cited scientist ...', 'href': 'https://www.erg.cuhk.edu.hk/erg/node/2915', 'body': 'Dr. Kaiming He , an alumnus of the IE PhD program in 2011, is an Associate Professor with tenure at MIT. His research areas include computer vision and deep learning. Dr. He was supervised by Prof. Sean Tang during his PhD study in Information Engineering at CUHK. Dr. He is best known for his work on Deep Residual Networks (ResNets), which is the most-cited paper of the twenty-first century ...'}]