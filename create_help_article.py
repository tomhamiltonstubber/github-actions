import argparse
import github


def run(issue_number):
    print(issue_number)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-issue', default='', type=str, help='The Issue number')
    kwargs, other = parser.parse_known_args()
    print(kwargs)
    print(other)
    run(kwargs.issue)
